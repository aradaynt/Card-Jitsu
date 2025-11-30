"""
Pytest configuration and shared fixtures for the Card-Jitsu test suite.

This module defines:
- A Flask application fixture configured for testing.
- A test client fixture for sending requests to the application.

These fixtures allow all test modules to run against an isolated,
in-memory SQLite database and a fresh Flask app context.
"""

import pytest
import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app import create_app
from cardjitsu.models import db

@pytest.fixture
def app():
    """
    Create a Flask application configured for testing.

    This fixture:
        - Initializes the Flask app using `create_app()`.
        - Enables test mode (`TESTING=True`).
        - Uses an in-memory SQLite database for isolation.
        - Creates all database tables before yielding.
        - Yields the application instance to the test.

    Yields:
        Flask: A Flask application instance configured for pytest.
    """
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['WTF_CSRF_ENABLED'] = False

    with app.app_context():
        db.create_all()

    yield app

@pytest.fixture
def client(app):
    """
    Return a test client for sending HTTP requests to the Flask app.

    Args:
        app (Flask): The Flask test application provided by the `app` fixture.

    Returns:
        FlaskClient: A client that can send requests to the app during testing.
    """
    return app.test_client()