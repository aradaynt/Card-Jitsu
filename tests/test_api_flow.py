import json
import uuid
from cardjitsu.models import User

def _auth_header(token: str) -> dict:
    return {'Authorization': f"Bearer {token}"}

def test_register_login_and_stats_update(app, client):
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