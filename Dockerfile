FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_NO_CACHE_DIR=1
ENV FLASK_APP=app.py

WORKDIR /workspace

RUN python -m pip install --upgrade pip

COPY docker/entrypoint.sh /usr/local/bin/axure-share-entrypoint
RUN chmod +x /usr/local/bin/axure-share-entrypoint

EXPOSE 7855

ENTRYPOINT ["axure-share-entrypoint"]
