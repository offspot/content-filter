"""Orchestrate a Caddy server via its admin API"""

import http
import urllib.parse

import requests

from contentfilter.constants import Conf

KIWIX_VIEWER_PREFIX = "/viewer"
DEFAULT_ENTRIES = [{"host": ["blocked"]}]


def get_url(path: str):
    return f"{Conf.caddy_api_endpoint}{path}"


class FilterEntry(dict):
    def __init__(self, host: str | None = None, path: str | None = None):
        kwargs = {}
        if host is not None:
            kwargs["host"] = [host]
        if path is not None:
            kwargs["path"] = [path]
        super().__init__(kwargs)

    def __hash__(self):
        return hash((self.get("host", [None])[0], self.get("path", [None])[0]))


def setup():
    """Initialize Caddy's config (installs named rule)"""
    resp = requests.get(get_url("/id/cfrules"), timeout=Conf.caddy_timeout)
    if resp.status_code == http.HTTPStatus.OK:
        return

    template = (
        Conf.src_root.joinpath("templates")
        .joinpath("blocked.html")
        .read_text()
        .replace("__SUPPORTED_LOCALES", str(list(Conf.supported_locales)))
        .replace("__DEFAULT_LOCALE", Conf.default_locale)
    )

    resp = requests.put(
        get_url(f"/config/apps/http/servers/{Conf.caddy_server_name}/routes/0"),
        json={
            "@id": "cfrules",
            # we need at least one entry otherwise
            # it matches every single request
            "match": DEFAULT_ENTRIES,
            "handle": [
                {
                    "@id": "cfrules-handler",
                    "handler": "static_response",
                    "body": template,
                    "status_code": "451",
                    "headers": {"Content-Type": ["text/html; charset=utf-8"]},
                }
            ],
        },
        timeout=Conf.caddy_timeout,
    )


def get_entry_for(url: str) -> FilterEntry:
    uri = urllib.parse.urlparse(url)
    host, path = None, uri.path

    if Conf.filter_respects_scheme:
        ...

    if Conf.filter_respects_host:
        host = uri.netloc

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
        # entry["path"] = [f"/content/{uri.fragment}"]
        path = f"/content/{uri.fragment}"

    return FilterEntry(
        host=host,
        path=path,
    )


def get_all_entries() -> list[FilterEntry]:
    resp = requests.get(get_url("/id/cfrules/match/"), timeout=0.5)
    resp.raise_for_status()
    return resp.json()


def block_only_those_urls(urls: list[str]):
    """Set Caddy's block list completely"""
    entries = {get_entry_for(url) for url in urls} or DEFAULT_ENTRIES
    try:
        requests.patch(get_url("/id/cfrules/match/"), json=list(entries), timeout=0.5)
    except requests.exceptions.ReadTimeout:
        pass


def block_many_urls(urls: list[str]):
    """Set Caddy's block list completely"""
    entries = get_all_entries()
    for url in urls:
        entry = get_entry_for(url)
        if entry not in entries:
            entries.append(entry)
    try:
        requests.patch(
            get_url("/id/cfrules/match/"),
            json=list(entries or DEFAULT_ENTRIES),
            timeout=0.5,
        )
    except requests.exceptions.ReadTimeout:
        pass


async def unblock_all_urls():
    """Set Caddy's block list completely"""
    try:
        requests.patch(get_url("/id/cfrules/match/"), json=DEFAULT_ENTRIES, timeout=0.5)
    except requests.exceptions.ReadTimeout:
        pass


async def block_url(url: str):
    """Add url to Caddy's block list"""
    try:
        requests.post(
            get_url("/id/cfrules/match/"), json=get_entry_for(url), timeout=0.5
        )
    except requests.exceptions.ReadTimeout:
        pass


async def unblock_url(url: str):
    """Remove url from Caddy's block list (currently replaces complete list)"""
    existing_entry = get_entry_for(url)

    try:
        for index, entry in enumerate(get_all_entries()):
            if entry == existing_entry:
                requests.delete(
                    get_url(f"/id/cfrules/match/{index}"), timeout=0.5
                ).raise_for_status()
                return
    except requests.exceptions.ReadTimeout:
        pass
