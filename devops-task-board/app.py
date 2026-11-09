import json
import logging
import os
import sys
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    stream=sys.stdout,
    force=True,
)

logger = logging.getLogger("devops-task-board")
logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

ROOT = Path(__file__).resolve().parent

TASKS = [
    {"id": 1, "title": "Build Docker image", "done": True},
    {"id": 2, "title": "Deploy application to Kubernetes", "done": False},
    {"id": 3, "title": "Configure Prometheus monitoring", "done": False},
]

LOCK = threading.Lock()
NEXT_ID = 4


class Handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        logger.info("%s %s", self.address_string(), fmt % args)

    def send_bytes(self, code, body, content_type="application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def respond(self, code, obj):
        self.send_bytes(code, json.dumps(obj).encode("utf-8"))

    def read_json(self):
        try:
            size = int(self.headers.get("Content-Length", "0"))

            if not 0 < size <= 4096:
                return None

            obj = json.loads(self.rfile.read(size))

            return obj if isinstance(obj, dict) else None

        except (ValueError, json.JSONDecodeError):
            return None

    def do_GET(self):
        path = urlparse(self.path).path

        if path in ("/healthcheck", "/readyz"):
            return self.respond(
                200,
                {
                    "status": ("healthy" if path == "/healthcheck" else "ready"),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )

        if path == "/api/tasks":
            with LOCK:
                tasks = [dict(t) for t in TASKS]

            return self.respond(200, {"tasks": tasks})

        files = {
            "/": ("index.html", "text/html; charset=utf-8"),
            "/static/styles.css": ("static/styles.css", "text/css; charset=utf-8"),
            "/static/app.js": (
                "static/app.js",
                "application/javascript; charset=utf-8",
            ),
            "/static/images/logo.svg": ("static/images/logo.svg", "image/svg+xml"),
            "/static/images/empty-state.svg": (
                "static/images/empty-state.svg",
                "image/svg+xml",
            ),
        }

        if path not in files:
            return self.respond(404, {"error": "Not found"})

        filename, content_type = files[path]

        return self.send_bytes(200, (ROOT / filename).read_bytes(), content_type)

    def do_POST(self):
        global NEXT_ID

        if urlparse(self.path).path != "/api/tasks":
            return self.respond(404, {"error": "Not found"})

        obj = self.read_json()
        title = obj.get("title") if obj else None

        if not isinstance(title, str) or not title.strip() or len(title.strip()) > 120:
            return self.respond(400, {"error": "Title must contain 1–120 characters"})

        with LOCK:
            task = {"id": NEXT_ID, "title": title.strip(), "done": False}

            NEXT_ID += 1
            TASKS.append(task)

        logger.info("Created task id=%s", task["id"])

        return self.respond(201, task)

    def do_PATCH(self):
        path = urlparse(self.path).path

        if not path.startswith("/api/tasks/"):
            return self.respond(404, {"error": "Not found"})

        try:
            task_id = int(path.rsplit("/", 1)[-1])
        except ValueError:
            return self.respond(404, {"error": "Not found"})

        obj = self.read_json()

        if not obj or not isinstance(obj.get("done"), bool):
            return self.respond(400, {"error": "done must be boolean"})

        with LOCK:
            for task in TASKS:
                if task["id"] == task_id:
                    task["done"] = obj["done"]
                    return self.respond(200, dict(task))

        return self.respond(404, {"error": "Task not found"})

    def do_DELETE(self):
        path = urlparse(self.path).path

        if not path.startswith("/api/tasks/"):
            return self.respond(404, {"error": "Not found"})

        try:
            task_id = int(path.rsplit("/", 1)[-1])
        except ValueError:
            return self.respond(404, {"error": "Not found"})

        with LOCK:
            for index, task in enumerate(TASKS):
                if task["id"] == task_id:
                    TASKS.pop(index)
                    return self.respond(200, {"deleted": task_id})

        return self.respond(404, {"error": "Task not found"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))

    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)

    logger.info("DevOps Task Board listening on port %s", port)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
