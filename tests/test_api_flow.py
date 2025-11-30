"""
Integration tests for the authentication and user-stat API flow.

These tests verify:
- User registration and login endpoints.
- JWT authentication behavior.
- Retrieval of `/api/me` statistics.
- Live updating of user stats in the database.
"""

import json
import uuid
from cardjitsu.models import User

def _auth_header(token: str) -> dict:
    """
    Return the Authorization header for a Bearer JWT token.

    Args:
        token (str): The JWT token returned by the login or register endpoint.

    Returns:
        dict: Header dictionary containing the properly formatted Authorization field.
    """
    return {'Authorization': f"Bearer {token}"}

def test_register_login_and_stats_update(app, client):
    """
    End-to-end test of register → login → stats retrieval → stats update.

    This test flow validates:
        1. A new user can register successfully (POST /api/register).
        2. The same user can log in and receive a valid JWT (POST /api/login).
        3. `/api/me` returns the correct default stats (0 wins, 0 games).
        4. Updating the user's stats directly in the database is reflected
           correctly when calling `/api/me` again.

    Args:
        app (Flask): The Flask application fixture.
        client (FlaskClient): The test client used to send API requests.
    """
    username = f"Aradtest_{uuid.uuid4().hex[:8]}"
    # Register
    response = client.post('/api/register', json={
        'username': username,
        'password': 'testpassword'
    })
    assert response.status_code == 201
    data = response.get_json()
    token = data['token']

    # Login
    response = client.post('/api/login', json={
        'username': username,
        'password': 'testpassword'
    })
    assert response.status_code == 200
    data = response.get_json()
    token = data['token']
    
    # check initial stats
    response = client.get('/api/me', headers=_auth_header(token))
    assert response.status_code == 200
    me = response.get_json()
    assert me['win_count'] == 0
    assert me['total_games'] == 0


    with app.app_context():
        u = User.query.filter_by(username=username).first()
        u.win_count = 5
        u.total_games = 10
        from cardjitsu.models import db
        db.session.commit()

    response = client.get('/api/me', headers=_auth_header(token))
    me = response.get_json()
    assert me['win_count'] == 5
    assert me['total_games'] == 10