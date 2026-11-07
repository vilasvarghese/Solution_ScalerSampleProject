
import importlib.util
import json
import os
import sys
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest


# --------------------------------------------------
# Locate and import application
# --------------------------------------------------

current_dir = os.path.dirname(os.path.abspath(__file__))

app_path = os.path.abspath(
    os.path.join(current_dir, "..", "app", "app.py")
)

if not os.path.exists(app_path):
    raise FileNotFoundError(
        f"Could not find app.py at {app_path}"
    )

spec = importlib.util.spec_from_file_location(
    "app_module",
    app_path
)

app = importlib.util.module_from_spec(spec)
sys.modules["app_module"] = app
spec.loader.exec_module(app)

Handler = app.Handler


# --------------------------------------------------
# Test Server Fixture
# --------------------------------------------------

@pytest.fixture(scope="module")
def test_server():
    """
    Start the application's HTTP server on a
    randomly allocated local port.
    """

    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        Handler
    )

    port = server.server_address[1]

    thread = threading.Thread(
        target=server.serve_forever,
        daemon=True
    )

    thread.start()

    yield f"http://127.0.0.1:{port}"

    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


# --------------------------------------------------
# Reset task data before each test
# --------------------------------------------------

@pytest.fixture(autouse=True)
def reset_tasks():
    """
    Ensure tests are independent by restoring
    the original application task state.
    """

    with app.LOCK:
        app.TASKS.clear()

        app.TASKS.extend([
            {
                "id": 1,
                "title": "Build Docker image",
                "done": True
            },
            {
                "id": 2,
                "title": "Deploy application to Kubernetes",
                "done": False
            },
            {
                "id": 3,
                "title": "Configure Prometheus monitoring",
                "done": False
            }
        ])

        app.NEXT_ID = 4


# --------------------------------------------------
# Helper for HTTP requests
# --------------------------------------------------

def make_request(
    base_url,
    path,
    method="GET",
    payload=None
):
    """
    Send HTTP requests and return:
    (status_code, response_body, headers)
    """

    headers = {}

    data = None

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(
        f"{base_url}{path}",
        data=data,
        headers=headers,
        method=method
    )

    try:
        response = urllib.request.urlopen(
            request,
            timeout=5
        )

    except urllib.error.HTTPError as error:
        response = error

    with response:
        body = response.read().decode("utf-8")

        return (
            response.status,
            body,
            response.headers
        )


# ==================================================
# HEALTH CHECK TESTS
# ==================================================

def test_healthcheck_status_200(test_server):

    status, body, headers = make_request(
        test_server,
        "/healthcheck"
    )

    assert status == 200


def test_healthcheck_response_body(test_server):

    status, body, headers = make_request(
        test_server,
        "/healthcheck"
    )

    data = json.loads(body)

    assert data["status"] == "healthy"


def test_healthcheck_content_type(test_server):

    status, body, headers = make_request(
        test_server,
        "/healthcheck"
    )

    assert "application/json" in headers.get(
        "Content-Type", ""
    )


def test_healthcheck_has_timestamp(test_server):

    status, body, headers = make_request(
        test_server,
        "/healthcheck"
    )

    data = json.loads(body)

    assert "timestamp" in data
    assert isinstance(data["timestamp"], str)


# ==================================================
# READINESS TESTS
# ==================================================

def test_readyz_status_200(test_server):

    status, body, headers = make_request(
        test_server,
        "/readyz"
    )

    assert status == 200


def test_readyz_response_body(test_server):

    status, body, headers = make_request(
        test_server,
        "/readyz"
    )

    data = json.loads(body)

    assert data["status"] == "ready"


# ==================================================
# TASK LISTING TESTS
# ==================================================

def test_get_tasks_status_200(test_server):

    status, body, headers = make_request(
        test_server,
        "/api/tasks"
    )

    assert status == 200


def test_get_tasks_returns_json(test_server):

    status, body, headers = make_request(
        test_server,
        "/api/tasks"
    )

    data = json.loads(body)

    assert "tasks" in data
    assert isinstance(data["tasks"], list)


def test_get_tasks_initial_count(test_server):

    status, body, headers = make_request(
        test_server,
        "/api/tasks"
    )

    data = json.loads(body)

    assert len(data["tasks"]) == 3


# ==================================================
# TASK CREATION TESTS
# ==================================================

def test_create_task_success(test_server):

    status, body, headers = make_request(
        test_server,
        "/api/tasks",
        method="POST",
        payload={
            "title": "Deploy application to EKS"
        }
    )

    data = json.loads(body)

    assert status == 201

    assert data["title"] == (
        "Deploy application to EKS"
    )

    assert data["done"] is False

    assert data["id"] == 4


def test_create_task_increases_count(test_server):

    make_request(
        test_server,
        "/api/tasks",
        method="POST",
        payload={
            "title": "Configure Grafana"
        }
    )

    status, body, headers = make_request(
        test_server,
        "/api/tasks"
    )

    data = json.loads(body)

    assert len(data["tasks"]) == 4


def test_create_task_empty_title(test_server):

    status, body, headers = make_request(
        test_server,
        "/api/tasks",
        method="POST",
        payload={
            "title": ""
        }
    )

    assert status == 400


def test_create_task_whitespace_title(test_server):

    status, body, headers = make_request(
        test_server,
        "/api/tasks",
        method="POST",
        payload={
            "title": "   "
        }
    )

    assert status == 400


def test_create_task_missing_title(test_server):

    status, body, headers = make_request(
        test_server,
        "/api/tasks",
        method="POST",
        payload={}
    )

    assert status == 400


def test_create_task_title_too_long(test_server):

    status, body, headers = make_request(
        test_server,
        "/api/tasks",
        method="POST",
        payload={
            "title": "A" * 121
        }
    )

    assert status == 400


def test_create_task_trims_whitespace(test_server):

    status, body, headers = make_request(
        test_server,
        "/api/tasks",
        method="POST",
        payload={
            "title": "  Configure ArgoCD  "
        }
    )

    data = json.loads(body)

    assert status == 201

    assert data["title"] == "Configure ArgoCD"


# ==================================================
# TASK UPDATE TESTS
# ==================================================

def test_mark_task_completed(test_server):

    status, body, headers = make_request(
        test_server,
        "/api/tasks/2",
        method="PATCH",
        payload={
            "done": True
        }
    )

    data = json.loads(body)

    assert status == 200

    assert data["id"] == 2

    assert data["done"] is True


def test_mark_task_incomplete(test_server):

    status, body, headers = make_request(
        test_server,
        "/api/tasks/1",
        method="PATCH",
        payload={
            "done": False
        }
    )

    data = json.loads(body)

    assert status == 200

    assert data["done"] is False


def test_update_nonexistent_task(test_server):

    status, body, headers = make_request(
        test_server,
        "/api/tasks/999",
        method="PATCH",
        payload={
            "done": True
        }
    )

    assert status == 404


def test_update_invalid_done_value(test_server):

    status, body, headers = make_request(
        test_server,
        "/api/tasks/1",
        method="PATCH",
        payload={
            "done": "yes"
        }
    )

    assert status == 400


# ==================================================
# TASK DELETION TESTS
# ==================================================

def test_delete_task_success(test_server):

    status, body, headers = make_request(
        test_server,
        "/api/tasks/2",
        method="DELETE"
    )

    data = json.loads(body)

    assert status == 200

    assert data["deleted"] == 2


def test_delete_task_reduces_count(test_server):

    make_request(
        test_server,
        "/api/tasks/2",
        method="DELETE"
    )

    status, body, headers = make_request(
        test_server,
        "/api/tasks"
    )

    data = json.loads(body)

    assert len(data["tasks"]) == 2


def test_delete_nonexistent_task(test_server):

    status, body, headers = make_request(
        test_server,
        "/api/tasks/999",
        method="DELETE"
    )

    assert status == 404


# ==================================================
# FRONTEND TESTS
# ==================================================

def test_homepage_status_200(test_server):

    status, body, headers = make_request(
        test_server,
        "/"
    )

    assert status == 200


def test_homepage_contains_title(test_server):

    status, body, headers = make_request(
        test_server,
        "/"
    )

    assert "DevOps Task Board" in body


def test_homepage_content_type(test_server):

    status, body, headers = make_request(
        test_server,
        "/"
    )

    assert "text/html" in headers.get(
        "Content-Type", ""
    )


# ==================================================
# STATIC FILE TESTS
# ==================================================

@pytest.mark.parametrize(
    "path,content_type",
    [
        ("/static/styles.css", "text/css"),
        (
            "/static/app.js",
            "application/javascript"
        ),
        (
            "/static/images/logo.svg",
            "image/svg+xml"
        ),
        (
            "/static/images/empty-state.svg",
            "image/svg+xml"
        )
    ]
)
def test_static_files(
    test_server,
    path,
    content_type
):

    status, body, headers = make_request(
        test_server,
        path
    )

    assert status == 200

    assert content_type in headers.get(
        "Content-Type", ""
    )

    assert len(body) > 0


# ==================================================
# ERROR HANDLING TESTS
# ==================================================

def test_unknown_route_returns_404(test_server):

    status, body, headers = make_request(
        test_server,
        "/unknown"
    )

    assert status == 404


def test_unknown_api_route_returns_404(test_server):

    status, body, headers = make_request(
        test_server,
        "/api/unknown"
    )

    assert status == 404


def test_invalid_task_id_returns_404(test_server):

    status, body, headers = make_request(
        test_server,
        "/api/tasks/invalid",
        method="DELETE"
    )

    assert status == 404


# ==================================================
# RESPONSE HEADER TESTS
# ==================================================

def test_security_header_present(test_server):

    status, body, headers = make_request(
        test_server,
        "/healthcheck"
    )

    assert headers.get(
        "X-Content-Type-Options"
    ) == "nosniff"


# ==================================================
# LOGGING TESTS
# ==================================================

def test_logger_exists():

    assert app.logger is not None

    assert app.logger.name == "devops-task-board"


def test_logging_configuration():

    assert app.logger.isEnabledFor(
        app.logging.INFO
    )

