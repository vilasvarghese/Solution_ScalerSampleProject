
# syntax=docker/dockerfile:1

# --------------------------------------------------
# 1. Minimal Python runtime
# --------------------------------------------------
# Pin this image to an approved digest in production.
FROM python:3.12-slim-bookworm

# --------------------------------------------------
# 2. Image metadata
# --------------------------------------------------
LABEL org.opencontainers.image.title="DevOps Task Board" \
      org.opencontainers.image.description="Python task management application" \
      org.opencontainers.image.vendor="DevOps Academy"

# --------------------------------------------------
# 3. Runtime configuration
# --------------------------------------------------
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=UTF-8 \
    PORT=8080

# --------------------------------------------------
# 4. Working directory
# --------------------------------------------------
WORKDIR /app

# --------------------------------------------------
# 5. Copy only required application files
# --------------------------------------------------
COPY --chown=65532:65532 app/app.py ./app.py
COPY --chown=65532:65532 app/index.html ./index.html
COPY --chown=65532:65532 app/static/ ./static/

# --------------------------------------------------
# 6. Run as a non-root user
# --------------------------------------------------
USER 65532:65532

# --------------------------------------------------
# 7. Application port
# --------------------------------------------------
EXPOSE 8080

# --------------------------------------------------
# 8. Container health check
# --------------------------------------------------
# Python is already installed in the base image.
# No need to install curl or wget.
HEALTHCHECK --interval=30s \
            --timeout=3s \
            --start-period=10s \
            --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8080') + '/healthcheck', timeout=2).close()" || exit 1

# --------------------------------------------------
# 9. Start application
# --------------------------------------------------
CMD ["python", "-u", "app.py"]
