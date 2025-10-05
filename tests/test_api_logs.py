import tempfile
from pathlib import Path
from yearplan.app import app, storage


def setup_temp_db(tmp_path):
    db = tmp_path / 'db.json'
    storage.path = db
    storage._data = {'goals': [], 'logs': []}


def test_goals_contains_status(tmp_path):
    setup_temp_db(tmp_path)
    gid = storage.add_goal_with_meta('API Test', start_date='2025-10-01', end_date='2025-10-10', target=100)
    client = app.test_client()
    r = client.get('/api/goals')
    assert r.status_code == 200
    data = r.get_json()
    assert isinstance(data, list)
    assert 'status' in data[0]


def test_edit_and_delete_log(tmp_path):
    setup_temp_db(tmp_path)
    gid = storage.add_goal_with_meta('EditDelete', start_date='2025-10-01', end_date='2025-10-10', target=10)
    # add a log
    entry = storage.add_log(gid, 'increment', value=1, ts='2025-10-02')
    lid = entry['id']
    client = app.test_client()

    # edit the log
    r = client.put(f'/api/logs/{lid}', json={'value': 5})
    assert r.status_code == 200
    ed = r.get_json()
    assert ed['value'] == 5

    # delete the log
    r2 = client.delete(f'/api/logs/{lid}')
    assert r2.status_code == 200
    assert r2.get_json().get('ok') is True
