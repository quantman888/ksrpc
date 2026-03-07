# syntax=docker/dockerfile:1.7
FROM python:3.13-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends tini \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

ARG KSRPC_PIP_PACKAGE=ksrpc
ARG PIP_EXTRA_INDEX_URL=
ARG PIP_TRUSTED_HOST=

COPY gunicorn.conf.py /app/gunicorn.conf.py

RUN --mount=type=secret,id=ksrpc_pip_conf,target=/etc/pip.conf,required=false \
    set -eu \
    && PIP_EXTRA_INDEX_URL="${PIP_EXTRA_INDEX_URL}" PIP_TRUSTED_HOST="${PIP_TRUSTED_HOST}" pip install --no-cache-dir "${KSRPC_PIP_PACKAGE}"

EXPOSE 8080

ENTRYPOINT ["tini", "--"]
CMD ["python", "-u", "-m", "gunicorn", "-c", "/app/gunicorn.conf.py", "ksrpc.run_gunicorn:web_app"]
