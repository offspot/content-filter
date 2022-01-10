# content-filter

[![CodeFactor](https://www.codefactor.io/repository/github/offspot/content-filter/badge)](https://www.codefactor.io/repository/github/offspot/content-filter)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

This tool is a **blacklist-based content censorship tool** for the by *Offspot* admins
to limit access to certain URLs served by said *Offspot*.

It is a docker container that offers a web UI to input and manage (CRUD) a list of
_to-be-blocked_ URLs.

This container then talks to a reverse proxy to update its configuration so the blocking
of the URL is automated.

At this stage, only a live Caddy reverse-proxy (using the admin API) is supported.

## Usage

Because of the strong dependency between the reverse proxy and the contentfilter, 
here's a sample docker compose file which relies on a Caddy reverse proxy offering two
services:

- [kiwix-serve](https://www.kiwix.org/en/downloads/kiwix-serve/) to serve ZIM files on /kiwix/
- the contentfilter UI on /contentfilter

```docker-compose
version: "2.2"
services:

  reverse-proxy:
    container_name: reverse-proxy
    image: caddy:2-alpine
    volumes:
      - "./Caddyfile-ip:/etc/caddy/Caddyfile:ro"
    command: caddy run --config /etc/caddy/Caddyfile --adapter caddyfile
    environment:
      KIWIX_LINK: kiwix:80
      CONTENTFILTER_LINK: content-filter:80
    ports:
      - "80:80"
    expose:
      - "2020"
    networks:
      - frontend
      - backend
    restart: always

  kiwix:
    container_name: kiwix
    image: kiwix/kiwix-tools:latest
    command: /bin/sh -c "kiwix-serve --nolibrarybutton --nodatealiases --blockexternal --urlRootLocation /kiwix/ /data/*.zim"
    volumes:
      - "/data:/data:ro"
    expose:
      - "80"
    networks:
      - backend
    restart: always

  content-filter:
    container_name: content-filter
    image: ghcr.io/offspot/content-filter:dev
    volumes:
      - "./urls.json:/data/urls.json:rw"
    expose:
      - "80"
    environment:
      DATABASE_PATH: /data/urls.json
      WEBROOT_PREFIX: /content-filter
      REVERSE_PROXY: caddy_live
      FILTER_RESPECTS_SCHEME: N
      FILTER_RESPECTS_HOST: N
      CADDY_ADMIN_URL: http://reverse-proxy:2020
      CADDY_SERVER_NAME: srv0
      ADMIN_PASSWORD: password
    depends_on:
      - reverse-proxy
    networks:
      - backend
    restart: always

networks:
  frontend:
  backend:

```

This would work with a Caddy configured as:

```Caddyfile
{
    # global options
    admin :2020
    auto_https disable_redirects
    local_certs
    skip_install_trust
}

:80 {
    # main, no host proxy
    redir / /kiwix permanent

    redir /kiwix /kiwix/ permanent
    reverse_proxy /kiwix/* {$KIWIX_LINK} {
    }

    redir /content-filter /content-filter/ permanent
    reverse_proxy /content-filter/* {$CONTENTFILTER_LINK} {
    }

    handle_errors {
        respond "HTTP {http.error.status_code} Error"
    }

    root * /tmp
    file_server browse
}
```

Please, take a look at [`constants.py`](https://github.com/offspot/content-filter/blob/main/src/contentfilter/constants.py) for configuration hints and [Open Issue](https://github.com/offspot/content-filter/issues/new) for documentation, feature requests and bug reports.


## devel

```sh
# pip install contentfilter  # we don't publish on PyPi
pip install uvicorn[default]
ADMIN_PASSWORD=password PYTHONPATH=src uvicorn "contentfilter.main:app"
```
