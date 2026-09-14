"""
Pytest configuration and session-wide fixtures for Canvas SpeedGrader test suites.
Provides ephemeral in-process mock server, authenticated sessions, clients, and synthetic submissions.
"""

import os
import tempfile
from typing import Generator
import pytest

from tests.harness import CanvasGradingClient, CanvasSession
from tests.mock_server import (
    MockCanvasServer,
    create_exp05_pdf,
    create_exp06_pdf,
    create_lab3_part_a_html,
    create_lab3_part_b_html,
    create_websnappr_png,
    mock_state,
)


@pytest.fixture(scope="session")
def mock_server() -> Generator[MockCanvasServer, None, None]:
    """Starts session-scoped threaded mock Canvas server on ephemeral port."""
    server = MockCanvasServer(host="127.0.0.1", port=0)
    server.start()
    yield server
    server.stop()


@pytest.fixture(scope="session")
def server_url(mock_server: MockCanvasServer) -> str:
    """Returns base URL for mock Canvas server."""
    return mock_server.base_url


@pytest.fixture(autouse=True)
def reset_server_state(mock_server: MockCanvasServer):
    """Ensures test independence: resets mock state before each test."""
    mock_server.reset()
    yield
    mock_server.reset()


@pytest.fixture
def auth_session() -> CanvasSession:
    """Returns authenticated CanvasSession with valid session cookie and CSRF token."""
    return CanvasSession(
        cookies=[
            {
                "name": "canvas_session",
                "value": "mock_authenticated_session_hash_abc123",
                "domain": "127.0.0.1",
                "path": "/",
                "secure": False,
                "httpOnly": True,
            },
            {
                "name": "_csrf_token",
                "value": "mock_token",
                "domain": "127.0.0.1",
                "path": "/",
                "secure": False,
                "httpOnly": False,
            },
        ],
        csrf_token="mock_token",
    )


@pytest.fixture
def grading_client(server_url: str, auth_session: CanvasSession) -> CanvasGradingClient:
    """Returns configured CanvasGradingClient targeting mock server."""
    return CanvasGradingClient(base_url=server_url, session=auth_session)


@pytest.fixture
def sample_exp05_pdf() -> bytes:
    return create_exp05_pdf()


@pytest.fixture
def sample_exp06_pdf() -> bytes:
    return create_exp06_pdf()


@pytest.fixture
def sample_lab3_html_a() -> str:
    return create_lab3_part_a_html()


@pytest.fixture
def sample_lab3_html_b() -> str:
    return create_lab3_part_b_html()


@pytest.fixture
def sample_websnappr_png() -> bytes:
    return create_websnappr_png()
