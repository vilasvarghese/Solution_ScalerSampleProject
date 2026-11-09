"""
Integration and API tests for DevOps Task Board.

Run from the repository root:

    python -m pytest test/ -v

The application is loaded from:
    devops-task-board/app.py
"""

import copy
import importlib.util
import json
import logging
import sys
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest


# ==================================================
# APPLICATION IMPORT
# ==================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_DIR = PROJECT_ROOT / "devops-task-board"
APP_PATH = APP_DIR / "app.py"

if not APP_PATH.is_file():
    raise FileNotFoundError(f"Application not found at {APP_PATH}")

spec = importlib.util.spec_from_file_location(
    "devops_task_board_app",
    APP_PATH,
)

if spec is None or spec.loader is None:
    raise ImportError(f"Unable to import application from {APP_PATH}")

app = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = app
spec.loader.exec_module(app)

Handler = app.Handler


# ==================================================
# INITIAL APPLICATION STATE
# ==================================================

# Capture initial tasks without assuming their titles
# or how many sample tasks exist.

with app.LOCK:
    INITIAL_TASKS = copy.deepcopy(app.TASKS)
    INITIAL_NEXT_ID = app.NEXT_ID


# ==================================================
# TEST FIXTURES
# ==================================================


@pytest.fixture(scope="module")
def test_server():
    """
    Start a real HTTP server on a random free port.

    Use the application directory as the working
    directory to support relative static file paths.
    """

    import os

    original_directory = Path.cwd()
    server = None
    thread = None

    try:
        os.chdir(APP_DIR)

        server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            Handler,
        )

        thread = threading.Thread(
            target=server.serve_forever,
            daemon=True,
        )

        thread.start()

        port = server.server_address[1]

        yield f"http://127.0.0.1:{port}"

    finally:
        if server is not None:
            server.shutdown()
            server.server_close()

        if thread is not None:
            thread.join(timeout=5)

        os.chdir(original_directory)


@pytest.fixture(autouse=True)
def reset_application_state():
    """
    Restore the original in-memory task state
    before and after every test.
    """

    def restore():
        with app.LOCK:
            app.TASKS.clear()
            app.TASKS.extend(copy.deepcopy(INITIAL_TASKS))
            app.NEXT_ID = INITIAL_NEXT_ID

    restore()

    yield

    restore()


# ==================================================
# HTTP REQUEST HELPER
# ==================================================


def make_request(
    base_url,
    path,
    method="GET",
    payload=None,
    raw_data=None,
    content_type=None,
):
    """
    Send a request to the application.

    Return:
        (status_code, response_body, headers)

    HTTP 4xx and 5xx responses are returned rather
    than raised, so tests can assert error behavior.
    """

    headers = {}
    data = None

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    elif raw_data is not None:
        data = raw_data

        if content_type is not None:
            headers["Content-Type"] = content_type

    request = urllib.request.Request(
        url=f"{base_url}{path}",
        data=data,
        headers=headers,
        method=method,
    )

    try:
        response = urllib.request.urlopen(
            request,
            timeout=5,
        )

    except urllib.error.HTTPError as error:
        response = error

    with response:
        response_body = response.read().decode("utf-8")

        return (
            response.status,
            response_body,
            response.headers,
        )


def get_json(base_url, path):
    """
    Request JSON and return the parsed object.
    """

    status, body, headers = make_request(
        base_url,
        path,
    )

    assert status == 200
    assert "application/json" in headers.get("Content-Type", "")

    return json.loads(body)


def create_task(base_url, title):
    """
    Create a task and return its JSON response.
    """

    status, body, headers = make_request(
        base_url,
        "/api/tasks",
        method="POST",
        payload={"title": title},
    )

    assert status == 201

    return json.loads(body)


# ==================================================
# HEALTH CHECK TESTS
# ==================================================


def test_healthcheck_returns_200(test_server):
    status, _, _ = make_request(
        test_server,
        "/healthcheck",
    )

    assert status == 200


def test_healthcheck_returns_healthy(test_server):
    data = get_json(
        test_server,
        "/healthcheck",
    )

    assert data["status"] == "healthy"


def test_healthcheck_contains_timestamp(test_server):
    data = get_json(
        test_server,
        "/healthcheck",
    )

    assert "timestamp" in data
    assert isinstance(data["timestamp"], str)
    assert data["timestamp"]


def test_healthcheck_content_type(test_server):
    status, _, headers = make_request(
        test_server,
        "/healthcheck",
    )

    assert status == 200
    assert "application/json" in headers.get("Content-Type", "")


# ==================================================
# READINESS TESTS
# ==================================================


def test_readiness_returns_200(test_server):
    status, _, _ = make_request(
        test_server,
        "/readyz",
    )

    assert status == 200


def test_readiness_returns_ready(test_server):
    data = get_json(
        test_server,
        "/readyz",
    )

    assert data["status"] == "ready"


def test_readiness_contains_timestamp(test_server):
    data = get_json(
        test_server,
        "/readyz",
    )

    assert "timestamp" in data


# ==================================================
# TASK LISTING TESTS
# ==================================================


def test_list_tasks_returns_200(test_server):
    status, _, _ = make_request(
        test_server,
        "/api/tasks",
    )

    assert status == 200


def test_list_tasks_returns_json(test_server):
    data = get_json(
        test_server,
        "/api/tasks",
    )

    assert "tasks" in data
    assert isinstance(data["tasks"], list)


def test_list_tasks_has_initial_data(test_server):
    data = get_json(
        test_server,
        "/api/tasks",
    )

    assert len(data["tasks"]) == len(INITIAL_TASKS)


def test_tasks_have_expected_fields(test_server):
    data = get_json(
        test_server,
        "/api/tasks",
    )

    assert data["tasks"]

    for task in data["tasks"]:
        assert "id" in task
        assert "title" in task
        assert "done" in task

        assert isinstance(task["id"], int)
        assert isinstance(task["title"], str)
        assert isinstance(task["done"], bool)


# ==================================================
# TASK CREATION TESTS
# ==================================================


def test_create_task_returns_201(test_server):
    status, _, _ = make_request(
        test_server,
        "/api/tasks",
        method="POST",
        payload={"title": "Deploy to Kubernetes"},
    )

    assert status == 201


def test_create_task_returns_correct_title(test_server):
    task = create_task(
        test_server,
        "Configure Prometheus",
    )

    assert task["title"] == "Configure Prometheus"


def test_new_task_is_incomplete(test_server):
    task = create_task(
        test_server,
        "Configure Grafana",
    )

    assert task["done"] is False


def test_new_task_has_numeric_id(test_server):
    task = create_task(
        test_server,
        "Create CI pipeline",
    )

    assert isinstance(task["id"], int)
    assert task["id"] > 0


def test_create_task_increases_count(test_server):
    before = get_json(
        test_server,
        "/api/tasks",
    )

    create_task(
        test_server,
        "Create Docker image",
    )

    after = get_json(
        test_server,
        "/api/tasks",
    )

    assert len(after["tasks"]) == (len(before["tasks"]) + 1)


def test_created_task_appears_in_listing(test_server):
    task = create_task(
        test_server,
        "Deploy with Argo CD",
    )

    data = get_json(
        test_server,
        "/api/tasks",
    )

    ids = [item["id"] for item in data["tasks"]]

    assert task["id"] in ids


def test_multiple_tasks_have_unique_ids(test_server):
    first = create_task(
        test_server,
        "Task A",
    )

    second = create_task(
        test_server,
        "Task B",
    )

    assert first["id"] != second["id"]


def test_create_task_trims_whitespace(test_server):
    task = create_task(
        test_server,
        "  Configure Argo CD  ",
    )

    assert task["title"] == "Configure Argo CD"


# ==================================================
# INPUT VALIDATION TESTS
# ==================================================


@pytest.mark.parametrize(
    "payload",
    [
        {"title": ""},
        {"title": "   "},
        {"title": "A" * 121},
        {"title": None},
        {"title": 123},
        {},
    ],
)
def test_invalid_task_titles_rejected(
    test_server,
    payload,
):
    status, _, _ = make_request(
        test_server,
        "/api/tasks",
        method="POST",
        payload=payload,
    )

    assert status == 400


def test_invalid_creation_does_not_add_task(
    test_server,
):
    before = get_json(
        test_server,
        "/api/tasks",
    )

    status, _, _ = make_request(
        test_server,
        "/api/tasks",
        method="POST",
        payload={"title": ""},
    )

    after = get_json(
        test_server,
        "/api/tasks",
    )

    assert status == 400
    assert len(after["tasks"]) == len(before["tasks"])


def test_title_at_maximum_length(test_server):
    task = create_task(
        test_server,
        "A" * 120,
    )

    assert len(task["title"]) == 120


# ==================================================
# TASK UPDATE TESTS
# ==================================================


def test_complete_task(test_server):
    task = create_task(
        test_server,
        "Complete Kubernetes lab",
    )

    status, body, _ = make_request(
        test_server,
        f"/api/tasks/{task['id']}",
        method="PATCH",
        payload={"done": True},
    )

    updated = json.loads(body)

    assert status == 200
    assert updated["id"] == task["id"]
    assert updated["done"] is True


def test_mark_task_incomplete(test_server):
    task = create_task(
        test_server,
        "Practice Docker",
    )

    make_request(
        test_server,
        f"/api/tasks/{task['id']}",
        method="PATCH",
        payload={"done": True},
    )

    status, body, _ = make_request(
        test_server,
        f"/api/tasks/{task['id']}",
        method="PATCH",
        payload={"done": False},
    )

    updated = json.loads(body)

    assert status == 200
    assert updated["done"] is False


def test_updated_task_persists_in_memory(test_server):
    task = create_task(
        test_server,
        "Review Kubernetes security",
    )

    make_request(
        test_server,
        f"/api/tasks/{task['id']}",
        method="PATCH",
        payload={"done": True},
    )

    data = get_json(
        test_server,
        "/api/tasks",
    )

    updated = next(item for item in data["tasks"] if item["id"] == task["id"])

    assert updated["done"] is True


def test_update_nonexistent_task_returns_404(
    test_server,
):
    status, _, _ = make_request(
        test_server,
        "/api/tasks/999999",
        method="PATCH",
        payload={"done": True},
    )

    assert status == 404


@pytest.mark.parametrize(
    "payload",
    [
        {"done": "yes"},
        {"done": 1},
        {"done": None},
        {},
    ],
)
def test_invalid_update_rejected(
    test_server,
    payload,
):
    task = create_task(
        test_server,
        "Update validation test",
    )

    status, _, _ = make_request(
        test_server,
        f"/api/tasks/{task['id']}",
        method="PATCH",
        payload=payload,
    )

    assert status == 400


# ==================================================
# TASK DELETION TESTS
# ==================================================


def test_delete_task_returns_200(test_server):
    task = create_task(
        test_server,
        "Temporary task",
    )

    status, _, _ = make_request(
        test_server,
        f"/api/tasks/{task['id']}",
        method="DELETE",
    )

    assert status == 200


def test_delete_task_returns_deleted_id(test_server):
    task = create_task(
        test_server,
        "Remove task",
    )

    status, body, _ = make_request(
        test_server,
        f"/api/tasks/{task['id']}",
        method="DELETE",
    )

    result = json.loads(body)

    assert status == 200
    assert result["deleted"] == task["id"]


def test_deleted_task_disappears(test_server):
    task = create_task(
        test_server,
        "Delete this task",
    )

    make_request(
        test_server,
        f"/api/tasks/{task['id']}",
        method="DELETE",
    )

    data = get_json(
        test_server,
        "/api/tasks",
    )

    assert all(item["id"] != task["id"] for item in data["tasks"])


def test_delete_nonexistent_task_returns_404(
    test_server,
):
    status, _, _ = make_request(
        test_server,
        "/api/tasks/999999",
        method="DELETE",
    )

    assert status == 404


# ==================================================
# FRONTEND TESTS
# ==================================================


def test_homepage_returns_200(test_server):
    status, _, _ = make_request(
        test_server,
        "/",
    )

    assert status == 200


def test_homepage_contains_app_name(test_server):
    _, body, _ = make_request(
        test_server,
        "/",
    )

    assert "DevOps Task Board" in body


def test_homepage_content_type(test_server):
    _, _, headers = make_request(
        test_server,
        "/",
    )

    assert "text/html" in headers.get("Content-Type", "")


# ==================================================
# STATIC FILE TESTS
# ==================================================


@pytest.mark.parametrize(
    "path,expected_content_type",
    [
        (
            "/static/styles.css",
            "text/css",
        ),
        (
            "/static/app.js",
            "javascript",
        ),
        (
            "/static/images/logo.svg",
            "image/svg+xml",
        ),
        (
            "/static/images/empty-state.svg",
            "image/svg+xml",
        ),
    ],
)
def test_static_files_served(
    test_server,
    path,
    expected_content_type,
):
    status, body, headers = make_request(
        test_server,
        path,
    )

    assert status == 200
    assert body
    assert expected_content_type in headers.get("Content-Type", "")


# ==================================================
# ERROR HANDLING TESTS
# ==================================================


def test_unknown_route_returns_404(test_server):
    status, _, _ = make_request(
        test_server,
        "/unknown",
    )

    assert status == 404


def test_unknown_api_route_returns_404(
    test_server,
):
    status, _, _ = make_request(
        test_server,
        "/api/unknown",
    )

    assert status == 404


def test_invalid_task_id_returns_404(test_server):
    status, _, _ = make_request(
        test_server,
        "/api/tasks/invalid",
        method="DELETE",
    )

    assert status == 404


# ==================================================
# RESPONSE SECURITY TESTS
# ==================================================


def test_content_type_options_header(test_server):
    _, _, headers = make_request(
        test_server,
        "/healthcheck",
    )

    assert headers.get("X-Content-Type-Options") == "nosniff"


# ==================================================
# LOGGING TESTS
# ==================================================


def test_application_logger_exists():
    assert hasattr(app, "logger")
    assert isinstance(
        app.logger,
        logging.Logger,
    )


def test_application_info_logging_enabled():
    assert app.logger.isEnabledFor(logging.INFO)
