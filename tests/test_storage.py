from yearplan.storage import YearPlanStorage
from pathlib import Path
import tempfile


def test_add_and_list(tmp_path: Path):
    db = tmp_path / 'db.json'
    s = YearPlanStorage(db)
    s.add_goal('Finish book')
    s.add_goal('Run 100 km')
    goals = s.list_goals()
    assert len(goals) == 2
    assert goals[0]['text'] == 'Finish book'
