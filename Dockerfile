FROM python:3.14-alpine
LABEL org.opencontainers.image.source=https://github.com/offspot/content-filter

ENV VIRTUAL_ENV=/usr/local/env

RUN \
    apk add --no-cache dumb-init \
    # python dependencies
    && python3 -m venv $VIRTUAL_ENV \
    && $VIRTUAL_ENV/bin/pip3 install --no-cache-dir -U pip

# Copy pyproject.toml and its dependencies
COPY pyproject.toml README.md /src/
COPY src/contentfilter/__about__.py /src/src/contentfilter/__about__.py

# Install Python dependencies
RUN $VIRTUAL_ENV/bin/pip install --no-cache-dir /src[scripts]

COPY src /src/src
COPY *.md /src/
COPY tasks.py /src/
COPY prestart.sh /usr/local/bin/entrypoint

WORKDIR /src
RUN \
    $VIRTUAL_ENV/bin/pip install --no-cache-dir /src \
    && $VIRTUAL_ENV/bin/invoke download-js \
    && rm -rf /src

EXPOSE 80

# make sure to mount it for it to persist
ENV DATABASE_PATH /data/urls.json

# use a prefix if you're proxying this on a subfolder
ENV WEBROOT_PREFIX ""

# caddy or nginx
ENV REVERSE_PROXY caddy_live

# Y/N whether to consider netloc in URL for filtering.
# otherwise, omits the domain and only produces path rules
ENV FILTER_RESPECTS_SCHEME Y
ENV FILTER_RESPECTS_HOST Y

# caddy's API endpoint (ex: http://caddy:2019) must be enabled in caddy conf
# content-filter will automatically update caddy config upon each change
# if this is set
ENV CADDY_ADMIN_URL ""

# name of the caddy `server` in the http/servers config to apply filtering to
ENV CADDY_SERVER_NAME srv0

# restrict allowed orgins
ENV ALLOWED_ORIGINS *

# internal
ENV APP_MODULE "contentfilter.main:app"
# DONT CHANGE: important as the Database is just a list
ENV MAX_WORKERS 1

ENTRYPOINT ["/usr/bin/dumb-init", "--", "/usr/local/bin/entrypoint"]
CMD ["/usr/local/env/bin/fastapi","run", "--port", "80", "--entrypoint", "contentfilter.main:app"]
