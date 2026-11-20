import gettext
import http
import secrets
import typing
import urllib.parse
import uuid
from pathlib import Path
from typing import Annotated

import jinja2
import orjson
from babel.support import Translations
from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
)
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from jinja2.environment import Environment
from jinja2.loaders import FileSystemLoader
from jinja2.utils import select_autoescape
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from contentfilter import caddy_live as cl
from contentfilter.__about__ import __description__, __title__, __version__
from contentfilter.constants import Conf, ReverseProxyType, logger
from contentfilter.database import database

TRANSLATIONS = {
    locale: Translations.load(Conf.locales_dir, locale)
    for locale in Conf.supported_locales
}


def _(message: str) -> str:
    return TRANSLATIONS[Conf.current_locale].gettext(message=message)


@jinja2.pass_context
def url_path_for(context: dict, name: str, **path_params: typing.Any) -> str:
    request = context["request"]
    return request.scope["router"].url_path_for(name, **path_params)


class PrettyJSONResponse(JSONResponse):
    def render(self, content: typing.Any) -> bytes:
        return orjson.dumps(database, option=orjson.OPT_INDENT_2)


def get_locale_for(request: Request) -> str:
    accept_language = request.headers.get("Accept-Language", "")
    # Extract language codes from header and strip regions (e.g., 'en-US' -> 'en')
    parsed_languages = [tag.split("-")[0] for tag in accept_language.split(",")]
    # Find the first matching language from our supported locales
    for lang in parsed_languages:
        if lang in Conf.supported_locales:
            return lang
    return Conf.default_locale


def encode(text):
    return text.encode("UTF-8").hex()


def decode(text):
    return bytes.fromhex(text).decode("UTF-8")


def uri_validator(url) -> str:
    try:
        uri = urllib.parse.urlparse(url)
        if uri.netloc in Conf.filter_protected_hosts:
            return ""

        # kiwix-serve viewer tweak
        # when using the kiwix-serve viewer, all paths are identical
        # and the content is hidden behing fragment.
        # instead of blocking the kiwix viewer altogether, we convert the URL
        # to the equivalent /content/ one
        if (
            uri.netloc == Conf.filter_kiwix_tweak_domain
            and uri.path == "/viewer"
            and uri.fragment
        ):
            uri = uri._replace(path=f"/content/{uri.fragment}")

        # remove client-local data
        uri = uri._replace(fragment="")
        uri = uri._replace(query="")
        uri = uri._replace(params="")
        return uri.geturl() + ("/" if not uri.path else "")
    except Exception:
        return ""


def flash(request: Request, message: typing.Any, category: str = "info") -> None:
    if "_messages" not in request.session:
        request.session["_messages"] = []
    request.session["_messages"].append({"message": message, "category": category})


def get_flashed_messages(request: Request):
    return request.session.pop("_messages") if "_messages" in request.session else []


async def on_change(added_url: str | None = None, removed_url: str | None = None):
    logger.debug(f"on_change {added_url=}, {removed_url=}")
    if Conf.reverse_proxy_type != ReverseProxyType.CADDY_LIVE:
        logger.debug("NOT LIVE")
        return

    if added_url:
        logger.debug(f"adding {added_url=}, to live")
        await cl.block_url(added_url)
    if removed_url:
        logger.debug(f"removing {removed_url=} from live")
        await cl.unblock_url(removed_url)


def setup():
    if Conf.reverse_proxy_type != ReverseProxyType.CADDY_LIVE:
        return

    # cleanup database
    for url in database:
        if new_url := uri_validator(url):
            if new_url != url:
                database.add(new_url)
                database.remove(url)
        else:
            database.remove(url)

    cl.setup()
    cl.block_only_those_urls(database)


class UrlItem(BaseModel):
    url: str


app = FastAPI(title=__title__, description=__description__, version=__version__)
webapp = FastAPI(title=__title__, description=__description__, version=__version__)
jinja_env = Environment(
    loader=FileSystemLoader(Conf.src_root.joinpath("templates")),
    autoescape=select_autoescape(["html", "xml", "txt"]),
    extensions=["jinja2.ext.i18n"],
)


@app.middleware("http")
async def set_locale(request: Request, call_next):
    locale = get_locale_for(request)
    Conf.current_locale = locale
    jinja_env.install_gettext_translations(TRANSLATIONS[locale])
    response = await call_next(request)
    jinja_env.uninstall_gettext_translations(TRANSLATIONS[locale])
    return response


webapp.mount(
    f"{Conf.webroot_prefix}/assets",
    StaticFiles(directory=Conf.assets_path),
    name="assets",
)
templates = Jinja2Templates(env=jinja_env)
templates.env.globals["get_flashed_messages"] = get_flashed_messages
templates.env.globals["url_path_for"] = url_path_for
templates.env.globals["conf"] = Conf
templates.env.filters["encode"] = encode

webapp.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
webapp.add_middleware(SessionMiddleware, secret_key=uuid.uuid4().hex)

# FastAPI way to automagically retrieve (await request.form()).get("xxx") from route def
FormDataFinder = Form(...)
FileFormFinder = File(...)
security = HTTPBasic()
SecurityDependency = Depends(security)


def get_current_username(credentials: HTTPBasicCredentials = SecurityDependency):
    correct_username = secrets.compare_digest(credentials.username, "admin")
    correct_password = secrets.compare_digest(credentials.password, Conf.admin_password)
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=http.HTTPStatus.UNAUTHORIZED,
            detail=_("Incorrect username or password"),
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


AuthDependency = Depends(get_current_username)


@webapp.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc):
    return PlainTextResponse(
        f"HTTP {exc.status_code}: {exc.detail}",
        status_code=exc.status_code,
        headers={"WWW-Authenticate": "Basic"} if exc.status_code == 401 else None,
    )


@webapp.get("/", response_class=HTMLResponse, name="home")
async def root(request: Request, username: str = AuthDependency):
    """Greetings"""
    return templates.TemplateResponse(
        request,
        "list.html",
        {"request": request, "page": "home", "urls": database, "username": username},
    )


@webapp.get("/logout", name="logout")
async def logout(request: Request):
    raise HTTPException(
        status_code=http.HTTPStatus.UNAUTHORIZED,
        detail=_("Incorrect username or password"),
        headers={"WWW-Authenticate": "Basic"},
    )


@webapp.get("/settings", response_class=HTMLResponse, name="settings")
async def settings(request: Request, username: str = AuthDependency):
    """Greetings"""
    return templates.TemplateResponse(
        request, "settings.html", {"request": request, "page": "settings"}
    )


@webapp.post("/add/", name="add_url")
async def add_url(
    request: Request,
    url: str = FormDataFinder,
    username: str = AuthDependency,
):
    logger.debug(f"ADDING {url=}")
    url = uri_validator(url)
    if not url:
        flash(request, _("Supplied URL is not a valid URL"), "danger")
    elif url in database:
        flash(request, _("This URL is already in the list"), "info")
    else:
        database.add(url)
        await on_change(added_url=url)
        flash(request, _("URL successfuly added to the list"), "success")
    return RedirectResponse(request.url_for("home"), status_code=http.HTTPStatus.FOUND)


@webapp.post("/edit/", name="edit_url")
async def edit_url(
    request: Request,
    url: Annotated[str, Form()],
    new_url: Annotated[str, Form()],
    username: str = AuthDependency,
):
    logger.debug(f"EDIT {url=} > {new_url=}")
    new_url = uri_validator(new_url)
    if not new_url:
        flash(request, _("Supplied URL is not a valid URL"), "danger")
    elif new_url in database:
        flash(
            request,
            _("Updated URL already in list. Remove this one instead"),
            "warning",
        )
    elif url not in database:
        flash(request, _("This URL is not in the list. Add it instead"), "info")
    else:
        index = database.index(url)
        database[index] = new_url
        await on_change(added_url=new_url, removed_url=url)
        flash(request, "URL successfuly updated", "success")
    return RedirectResponse(request.url_for("home"), status_code=http.HTTPStatus.FOUND)


@webapp.post("/remove/all", name="remove_all_urls")
async def clear_urls(
    request: Request,
    username: str = AuthDependency,
):
    redir_resp = RedirectResponse(
        request.url_for("settings"), status_code=http.HTTPStatus.FOUND
    )
    try:
        num_urls = len(database)
        database.clear()
        await cl.unblock_all_urls()
        if num_urls:
            flash(
                request,
                _("Successfully removed %(num_urls)s blocked URL(s) from the list")
                % {"num_urls": num_urls},
                "success",
            )
        else:
            flash(request, _("The list was already empty"), "info")
    except Exception as exc:
        flash(request, _("Unable to remove URLs: %(exc)s.") % {"exc": exc}, "danger")
    return redir_resp


app.mount(Conf.webroot_prefix, webapp)


@webapp.get("/remove/{url}", name="remove_url")
async def remove_url(request: Request, url: str, username: str = AuthDependency):
    url = decode(url)
    logger.debug(f"REMOVE {url=}")
    if url in database:
        database.remove(url)
        await on_change(removed_url=url)
        flash(request, _("URL successfuly removed from the list"), "success")
    else:
        flash(request, _("This URL wasn't in the list"), "info")
    return RedirectResponse(request.url_for("home"), status_code=http.HTTPStatus.FOUND)


@webapp.get("/export/raw.json", name="export_json")
async def export_json(request: Request, username: str = AuthDependency):
    return PrettyJSONResponse(
        content=database,
        headers={
            "Content-Disposition": 'attachment; filename="content-filter_export.json"'
        },
    )


@webapp.post("/import/", name="import_json")
async def import_json(
    request: Request,
    file: UploadFile = FileFormFinder,
    username: str = AuthDependency,
):
    redir_resp = RedirectResponse(
        request.url_for("settings"), status_code=http.HTTPStatus.FOUND
    )
    logger.info("RECEIVED FILE ?")
    try:
        content = await file.read()
        urls = orjson.loads(content)
        if not isinstance(urls, list):
            raise TypeError(f"JSON document is not a list: {type(urls)}")
    except Exception as exc:
        flash(
            request, _("Unable to import this file: %(exc)s.") % {"exc": exc}, "danger"
        )
        return redir_resp

    good_urls = [uri_validator(url) for url in urls]
    good_urls = [url for url in good_urls if url not in database]
    if good_urls:
        cl.block_many_urls(good_urls)
        for url in good_urls:
            database.add(url)
        flash(
            request,
            _("Successfuly imported %(num_urls)s URLs into the list")
            % {"num_urls": len(good_urls)},
            "success",
        )
    else:
        flash(
            request,
            _("No URL imported from that file. Was it empty? Duplicates?"),
            "warning",
        )
    return redir_resp
