""" Orchestrate a Caddy server via its admin API """

import http
import typing
import urllib.parse

import requests

from contentfilter.constants import Conf, logger
from contentfilter.database import database


def get_url(path: str):
    return f"{Conf.caddy_api_endpoint}{path}"


def setup():
    """Initialize Caddy's config (installs named rule)"""
    resp = requests.get(get_url("/id/cfrules"))
    if resp.status_code == http.HTTPStatus.OK:
        return

    with open(Conf.src_root / "templates" / "blocked.html") as fh:
        template = fh.read()

    resp = requests.put(
        get_url(f"/config/apps/http/servers/{Conf.caddy_server_name}/routes/0"),
        json={
            "@id": "cfrules",
            "match": [{"host": ["blocked"]}],
            "handle": [
                {
                    "@id": "cfrules-handler",
                    "handler": "static_response",
                    "body": template,
                }
            ],
        },
    )
    logger.debug(f"SETUP CODE {resp.status_code=}")
    logger.debug(f"SETUP RESP BODY {resp.text=}")


def block_all_urls(urls: typing.List[str]):
    """Set Caddy's block list completely"""
    entries = []
    for url in urls:
        uri = urllib.parse.urlparse(url)
        entry = {"path": [uri.path]}
        if Conf.filter_respects_scheme:
            ...
        if Conf.filter_respects_host:
            entry["host"] = [uri.netloc]
        entries.append(entry)
    if not entries:
        entries.append({"host": "test.blocked"})
    try:
        requests.patch(get_url("/id/cfrules/match/"), json=entries, timeout=0.5)
    except requests.exceptions.ReadTimeout:
        pass


async def block_url(url: str):
    """Add url to Caddy's block list (currently replaces complete list)"""
    block_all_urls(database)
    # uri = urllib.parse.urlparse(url)
    # entry = {"path": [uri.path]}
    # if Conf.filter_respects_scheme:
    #     ...
    # if Conf.filter_respects_host:
    #     entry["host"] = [uri.netloc]

    # try:
    #     requests.post(get_url("/id/cfrules/match/"), json=entry, timeout=0.5)
    # except requests.exceptions.ReadTimeout:
    #     pass


async def unblock_url(url: str):
    """Remove url from Caddy's block list (currently replaces complete list)"""
    block_all_urls(database)
