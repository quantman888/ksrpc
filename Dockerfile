FROM python:3.13-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends tini \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CONFIG=""

COPY . /app

RUN pip install --no-cache-dir .

EXPOSE 8080

ENTRYPOINT ["tini", "--"]
CMD ["python", "-u", "-m", "gunicorn", "-c", "/app/gunicorn.conf.py", "ksrpc.run_gunicorn:web_app"]
