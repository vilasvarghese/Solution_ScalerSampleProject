
# syntax=docker/dockerfile:1

# ============================================
# DevOps Task Board - Production-Oriented Image
# ============================================

FROM python:3.12-slim-bookworm

# --------------------------------------------
# Image metadata
# --------------------------------------------

LABEL org.opencontainers.image.title="DevOps Task Board" \
      org.opencontainers.image.description="Python task management web application" \
      org.opencontainers.image.vendor="DevOps Academy"

# --------------------------------------------
# Python runtime configuration
# --------------------------------------------

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=UTF-8 \
    PORT=8080 \
    HOME=/app

# --------------------------------------------
# Application working directory
# --------------------------------------------

WORKDIR /app

# --------------------------------------------
# Copy only required application files
# --------------------------------------------

COPY --chown=65532:65532 \
    devops-task-board/app.py \
    ./app.py

COPY --chown=65532:65532 \
    devops-task-board/index.html \
    ./index.html

COPY --chown=65532:65532 \
    devops-task-board/static/ \
    ./static/

# --------------------------------------------
# Drop root privileges
# --------------------------------------------

USER 65532:65532

# --------------------------------------------
# Application port
# --------------------------------------------

EXPOSE 8080

# --------------------------------------------
# Docker health check
# --------------------------------------------

HEALTHCHECK \
    --interval=30s \
    --timeout=3s \
    --start-period=10s \
    --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8080') + '/healthcheck', timeout=2).close()" || exit 1

# --------------------------------------------
# Application entrypoint
# --------------------------------------------

CMD ["python", "-u", "app.py"]
