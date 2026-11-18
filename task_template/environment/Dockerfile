# Example for a Maven project; adjust base image and build for your repo.
FROM maven:3.9-eclipse-temurin-17
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
ARG REPO_URL=https://github.com/OWNER/REPO
ARG BASE_COMMIT=REPLACE_WITH_FULL_SHA
RUN git clone "$REPO_URL" . && git checkout "$BASE_COMMIT" \
    && git config --global --add safe.directory /app
# Warm the dependency cache so tests can run quickly (and offline if needed).
RUN mvn -q -B -DskipTests dependency:go-offline install || true
CMD ["/bin/bash"]
