#!/bin/bash
set -e

CONTAINER_NAME="research-paper-rag-container"
MAX_ATTEMPTS="${VALIDATE_MAX_ATTEMPTS:-30}"
SLEEP_SECONDS="${VALIDATE_SLEEP_SECONDS:-5}"

for attempt in $(seq 1 "${MAX_ATTEMPTS}"); do
    if ! docker container inspect "${CONTAINER_NAME}" >/dev/null 2>&1; then
        echo "Container ${CONTAINER_NAME} is not present." >&2
        exit 1
    fi

    status=$(docker inspect \
        --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}unknown{{end}}' \
        "${CONTAINER_NAME}")
    echo "Health check attempt ${attempt}/${MAX_ATTEMPTS}: ${status}"

    if [ "${status}" = "healthy" ]; then
        echo "Research Paper RAG container is healthy."
        exit 0
    fi

    sleep "${SLEEP_SECONDS}"
done

echo "Container did not become healthy within the validation window." >&2
docker logs --tail 200 "${CONTAINER_NAME}" >&2 || true
exit 1
