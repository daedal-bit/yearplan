from pathlib import Path
import tempfile
from yearplan.storage import YearPlanStorage
from datetime import date


def test_progress_in_track():
    tf = Path(tempfile.mkdtemp()) / 'db.json'
    s = YearPlanStorage(tf)

    # create a 10-day plan with target 100 from 2025-10-01 to 2025-10-10
    gid = s.add_goal_with_meta('Test', start_date='2025-10-01', end_date='2025-10-10', target=100)

    # on day 5 (2025-10-05) expected progress = 100*(5/10)=50
    today = date.fromisoformat('2025-10-05')

    # no logs yet -> progress 0 -> not in track
    status = s.goal_progress_status(gid, today=today)
    assert status['expected'] == 50.0
    assert status['progress'] == 0
    assert status['in_track'] is False

    # add logs totalling 60
    s.add_log(gid, 'increment', value=20, ts='2025-10-02')
    s.add_log(gid, 'increment', value=40, ts='2025-10-04')

    status2 = s.goal_progress_status(gid, today=today)
    assert status2['progress'] == 60.0
    assert status2['expected'] == 50.0
    assert status2['in_track'] is True
