FROM python:3.8-slim-buster
LABEL org.opencontainers.image.source https://github.com/offspot/content-filter

# install wget for next step
RUN apt-get update -y \
    && apt-get install -y --no-install-recommends curl unzip build-essential make \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
# download files from (upstream) tiangolo/uvicorn-gunicorn-docker
RUN curl -L -O https://github.com/tiangolo/uvicorn-gunicorn-docker/archive/refs/heads/master.zip && \
    unzip master.zip && \
    mv uvicorn-gunicorn-docker-master/docker-images/* /tmp && \
    rm -rf ./uvicorn-gunicorn-docker-master && \
    rm -f ./master.zip

# install already-built wheels on arm to save 20mn!
RUN if [ "$TARGETARCH" = "arm32v7" ] ; then pip install \
    http://download.kiwix.org/dev/PyYAML-6.0-cp38-cp38-linux_armv7l.whl \
    http://download.kiwix.org/dev/uvloop-0.16.0-cp38-cp38-linux_armv7l.whl \
    http://download.kiwix.org/dev/httptools-0.2.0-cp38-cp38-linux_armv7l.whl \
    http://download.kiwix.org/dev/websockets-10.1-cp38-cp38-linux_armv7l.whl ; fi


# execute steps from upstam
RUN pip install --no-cache-dir -r /tmp/requirements.txt && \
    mv /tmp/start.sh /start.sh && \
    chmod +x /start.sh && \
    mv /tmp/gunicorn_conf.py /gunicorn_conf.py && \
    mv /tmp/start-reload.sh /start-reload.sh && \
    chmod +x /start-reload.sh && \
    mv /tmp/app /app

WORKDIR /app/
ENV PYTHONPATH=/app
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
