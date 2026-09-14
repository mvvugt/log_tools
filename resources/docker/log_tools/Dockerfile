FROM pandoc/minimal:3.8.2.1-static AS pandoc
FROM python:3.13-slim

ENV DEBIAN_FRONTEND=noninteractive

COPY --from=pandoc /usr/local/bin/pandoc /usr/local/bin/pandoc

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        git \
        make \
        sed && \
    rm -rf /var/lib/apt/lists/*

RUN python -m pip install --no-cache-dir --upgrade pip

WORKDIR /workspace
