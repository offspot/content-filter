import logging
import os
import pathlib
from dataclasses import dataclass
from enum import Enum
from typing import Optional

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("cf")
yesno = ("Y", "1", "yes", "on")


class ReverseProxyType(Enum):
    CADDY_LIVE = "caddy_live"
    CADDY_JSON = "caddy_json"
    CADDYFILE = "caddyfile"
    NGINX = "nginx"


@dataclass
class Conf:
    src_root: pathlib.Path = pathlib.Path(__file__).parent
    database_path: pathlib.Path = pathlib.Path(os.getenv("DATABASE_PATH", "urls.json"))
    webroot_prefix: str = os.getenv("WEBROOT_PREFIX", "").strip()
    reverse_proxy_type: ReverseProxyType = getattr(
        ReverseProxyType, os.getenv("REVERSE_PROXY", "caddyfile").upper()
    )
    filter_respects_scheme: bool = (
        os.getenv("FILTER_RESPECTS_SCHEME", "").upper() in yesno
    )
    filter_respects_host: bool = os.getenv("FILTER_RESPECTS_HOST", "").upper() in yesno
    caddy_api_endpoint: Optional[str] = os.getenv("CADDY_ADMIN_URL", "").strip() or None
    caddy_server_name: Optional[str] = os.getenv("CADDY_SERVER_NAME", "").strip()
    allowed_origins = os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost|http://localhost:8000|http://localhost:8080",  # dev fallback
    ).split("|")
    auth_secret: str = os.getenv("AUTH_SECRET", os.urandom(24).hex())
    admin_password: str = os.getenv("ADMIN_PASSWORD", os.urandom(4).hex())

    def __post_init__(self):
        ...
