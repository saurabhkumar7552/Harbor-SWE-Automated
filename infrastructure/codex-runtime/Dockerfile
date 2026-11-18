# BASE_IMAGE = the locally built task image (docker build -t <name> tasks/<task>/environment)
ARG BASE_IMAGE=harbor-brace-task:latest
FROM ${BASE_IMAGE}
ARG NODE_VERSION=22.22.0
ARG CODEX_VERSION=0.167.2
RUN curl -fsSL "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.gz" -o /tmp/node.tar.gz \
    && tar -xzf /tmp/node.tar.gz -C /usr/local --strip-components=1 \
    && rm /tmp/node.tar.gz \
    && npm install -g "@openai/codex@${CODEX_VERSION}" \
    && codex --version
RUN apt-get update && apt-get install -y --no-install-recommends ripgrep \
    && rm -rf /var/lib/apt/lists/*
