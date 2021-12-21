FROM tiangolo/uvicorn-gunicorn:python3.8-slim
LABEL org.opencontainers.image.source https://github.com/offspot/content-filter

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

# launched by upstream /start.sh
COPY prestart.sh /app/prestart.sh
RUN chmod +x /app/prestart.sh

# reove from upstream image
RUN rm -f /app/main.py

WORKDIR /tmp
RUN pip install --no-cache-dir --upgrade pip setuptools toml invoke
COPY pyproject.toml README.md setup.cfg setup.py tasks.py /tmp/
RUN invoke install-deps --package runtime
RUN invoke download-js
COPY src/ /tmp/src
RUN python setup.py install && mv /tmp/src /src
WORKDIR /src

# from upsteam
CMD ["/start.sh"]