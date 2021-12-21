#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4 nu

import http
import secrets
import typing
import urllib.parse
import uuid

import jinja2
import orjson
from fastapi import (
    FastAPI,
    HTTPException,
    Request,
    Form,
    UploadFile,
    File,
    Depends,
)
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware
from fastapi.responses import PlainTextResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from contentfilter import __description__, __title__, __version__
from contentfilter.constants import Conf, ReverseProxyType, logger
from contentfilter.database import database
from contentfilter import caddy_live as cl


@jinja2.pass_context
def url_path_for(context: dict, name: str, **path_params: typing.Any) -> str:
    request = context["request"]
    return request.scope["router"].url_path_for(name, **path_params)


class PrettyJSONResponse(JSONResponse):
    def render(self, content: typing.Any) -> bytes:
        return orjson.dumps(
            database, option=orjson.OPT_APPEND_NEWLINE | orjson.OPT_INDENT_2
        )


def encode(text):
    return text.encode("UTF-8").hex()


def decode(text):
    return bytes.fromhex(text).decode("UTF-8")


def uri_validator(url):
    try:
        result = urllib.parse.urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


def flash(request: Request, message: typing.Any, category: str = "info") -> None:
    if "_messages" not in request.session:
        request.session["_messages"] = []
    request.session["_messages"].append({"message": message, "category": category})


def get_flashed_messages(request: Request):
    return request.session.pop("_messages") if "_messages" in request.session else []


async def on_change(
    added_url: typing.Optional[str] = None, removed_url: typing.Optional[str] = None
):
    logger.debug(f"on_change {added_url=}, {removed_url=}")
    if Conf.reverse_proxy_type != ReverseProxyType.CADDY_LIVE:
        logger.debug("NOT LIVVVVVVEE")
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

    cl.setup()
    cl.block_all_urls(database)


class UrlItem(BaseModel):
    url: str


app = FastAPI(title=__title__, description=__description__, version=__version__)
webapp = FastAPI(title=__title__, description=__description__, version=__version__)

webapp.mount(
    f"{Conf.webroot_prefix}/assets",
    StaticFiles(directory=Conf.src_root.joinpath("assets")),
    name="assets",
)
templates = Jinja2Templates(directory=Conf.src_root.joinpath("templates"))
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
            detail="Incorrect username or password",
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
        "list.html",
        {"request": request, "page": "home", "urls": database, "username": username},
    )


@webapp.get("/logout", name="logout")
async def logout(request: Request):
    raise HTTPException(
        status_code=http.HTTPStatus.UNAUTHORIZED,
        detail="Incorrect username or password",
        headers={"WWW-Authenticate": "Basic"},
    )


@webapp.get("/settings", response_class=HTMLResponse, name="settings")
async def settings(request: Request, username: str = AuthDependency):
    """Greetings"""
    return templates.TemplateResponse(
        "settings.html", {"request": request, "page": "settings"}
    )


@webapp.post("/add/", name="add_url")
async def add_url(
    request: Request,
    url: str = FormDataFinder,
    username: str = AuthDependency,
):
    logger.debug(f"ADDING {url=}")
    if not uri_validator(url):
        flash(request, "Supplied URL is not a valid URL", "danger")
    elif url in database:
        flash(request, "This URL is already in the list", "info")
    else:
        database.add(url)
        await on_change(added_url=url)
        flash(request, "URL successfuly added to the list", "success")
    return RedirectResponse(request.url_for("home"), status_code=http.HTTPStatus.FOUND)


@webapp.post("/edit/{url}", name="edit_url")
async def edit_url(
    request: Request,
    url: str,
    new_url: str = FormDataFinder,
    username: str = AuthDependency,
):
    url = decode(url)
    logger.debug(f"EDIT {url=} > {new_url=}")
    if not uri_validator(new_url):
        flash(request, "Supplied URL is not a valid URL", "danger")
    elif not new_url:
        flash(request, "Missing URL", "warning")
    elif new_url in database:
        flash(request, "Updated URL already in list. Remove it instead", "warning")
    elif url not in database:
        flash(request, "This URL `{url}` is not in the list. Add it instead", "info")
    else:
        index = database.index(url)
        database[index] = new_url
        await on_change(added_url=new_url, removed_url=url)
        flash(request, "URL successfuly updated", "success")
    return RedirectResponse(request.url_for("home"), status_code=http.HTTPStatus.FOUND)


@webapp.get("/remove/{url}", name="remove_url")
async def remove_url(request: Request, url: str, username: str = AuthDependency):
    url = decode(url)
    logger.debug(f"REMOVE {url=}")
    if url in database:
        database.remove(url)
        await on_change(removed_url=url)
        flash(request, "URL successfuly removed from the list", "success")
    else:
        flash(request, "This URL wasn't in the list", "info")

    return RedirectResponse(request.url_for("home"), status_code=http.HTTPStatus.FOUND)


@webapp.get("/export/raw.json", name="export_json")
async def export_json(request: Request, username: str = AuthDependency):
    return PrettyJSONResponse(content=database)


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
            raise ValueError(f"JSON document is not a list: {type(urls)}")
    except Exception as exc:
        flash(request, f"Unable to import this file: {exc}.", "danger")
        return redir_resp

    nb_imported = 0
    for url in urls:
        if url not in database:
            if not uri_validator(url):
                continue
            database.add(url)
            nb_imported += 1
    if nb_imported:
        flash(
            request, f"Successfuly imported {nb_imported} URLs into the list", "success"
        )
    else:
        flash(
            request,
            "No URL imported from that file. Was it empty? Duplicates?",
            "warning",
        )
    return redir_resp


app.mount(Conf.webroot_prefix, webapp)
