FROM python:3.13-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends tini \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CONFIG=""

ARG KSRPC_PIP_PACKAGE=.
ARG PIP_INDEX_URL=
ARG PIP_EXTRA_INDEX_URL=
ARG PIP_TRUSTED_HOST=

COPY . /app

RUN set -eu \
    && PIP_INDEX_URL="${PIP_INDEX_URL}" PIP_EXTRA_INDEX_URL="${PIP_EXTRA_INDEX_URL}" PIP_TRUSTED_HOST="${PIP_TRUSTED_HOST}" pip install --no-cache-dir "${KSRPC_PIP_PACKAGE}" \
    && if [ "${KSRPC_PIP_PACKAGE}" != "." ]; then rm -rf /app/ksrpc; fi

EXPOSE 8080

ENTRYPOINT ["tini", "--"]
CMD ["python", "-u", "-m", "gunicorn", "-c", "/app/gunicorn.conf.py", "ksrpc.run_gunicorn:web_app"]
