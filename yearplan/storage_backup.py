from pathlib import Path
import json
from datetime import date, datetime
from typing import Optional


class YearPlanStorage:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._data = None
        self._load()

    def _load(self):
        if not self.path.exists():
            self._data = {'goals': []}
            return
        try:
            with     def get_user_by_id(self, user_id: int):
        \"\"\"Get user by ID\"\"\"
        for user in self._data.get('users', []):
            if user.get('id') == user_id:
                return user
        return None

    def user_owns_log(self, log_id: int, user_id: int) -> bool:
        \"\"\"Check if user owns the goal that this log belongs to\"\"\"
        # Find the log
        for log in self._data.get('logs', []):
            if log.get('id') == log_id:
                goal_id = log.get('goal_id')
                if goal_id:
                    goal = self.get_goal(goal_id, user_id)
                    return goal is not None
                return False
        return Falseelf.path, 'r', encoding='utf-8') as fh:
                self._data = json.load(fh)
        except Exception:
            self._data = {'goals': []}

    def _save(self):
        try:
            with open(self.path, 'w', encoding='utf-8') as fh:
                json.dump(self._data, fh, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

    def add_goal(self, text: str, user_id: int = None):
        # kept for backward-compat: simple add_goal(text)
        gid = self._next_id('goal')
        self._data['goals'].append({'id': gid, 'text': text, 'created_at': None, 'user_id': user_id})
        self._save()
        return gid

    def add_goal_with_meta(self, text: str, start_date: Optional[str] = None, end_date: Optional[str] = None, target: Optional[float] = None, task_type: str = 'increment', user_id: int = None):
        """Add a goal with optional scheduling/target metadata.

        Dates should be ISO strings (YYYY-MM-DD) or None. Target is a numeric goal total.
        task_type can be: 'increment' (count up), 'decrement' (count down), 'percentage' (0-100%).
        """
        gid = self._next_id('goal')
        entry = {
            'id': gid,
            'text': text,
            'created_at': date.today().isoformat(),
            'start_date': start_date,
            'end_date': end_date,
            'target': target,
            'task_type': task_type,
            'current_value': target if task_type == 'decrement' else 0,  # Start at target for decrement, 0 for others
            'user_id': user_id
        }
        self._data['goals'].append(entry)
        self._save()
        return gid

    def list_goals(self, user_id: int = None):
        goals = self._data.get('goals', [])
        if user_id is not None:
            goals = [g for g in goals if g.get('user_id') == user_id]
        return list(goals)

    def _next_id(self, prefix='id'):
        # create a simple incrementing id
        max_id = 0
        for g in self._data.get('goals', []):
            if isinstance(g.get('id'), int) and g['id'] > max_id:
                max_id = g['id']
        for l in self._data.get('logs', []):
            if isinstance(l.get('id'), int) and l['id'] > max_id:
                max_id = l['id']
        return max_id + 1

    def get_goal(self, goal_id: int, user_id: int = None):
        for g in self._data.get('goals', []):
            if g.get('id') == goal_id:
                if user_id is not None and g.get('user_id') != user_id:
                    return None  # User doesn't own this goal
                return g
        return None

    def _calculate_current_value(self, goal_id: int) -> float:
        """Calculate current value based on goal type and logs"""
        goal = self.get_goal(goal_id)
        if not goal:
            return 0.0
            
        task_type = goal.get('task_type', 'increment')
        target = goal.get('target', 0)
        
        if task_type == 'increment':
            # Sum all increments and subtract decrements (for rollbacks)
            total = 0.0
            for l in self._data.get('logs', []):
                if l.get('goal_id') == goal_id:
                    action = l.get('action')
                    v = l.get('value', 1)
                    try:
                        value = float(v) if v is not None else 0.0
                        if action in ['increment', 'update']:
                            total += value
                        elif action == 'decrement':  # This handles rollbacks of increments
                            total -= value
                    except Exception:
                        continue
            return max(0, total)  # Don't go below 0
            
        elif task_type == 'decrement':
            # Start at target, subtract decrements, add increments (for rollbacks)
            current = float(target or 0)
            for l in self._data.get('logs', []):
                if l.get('goal_id') == goal_id:
                    action = l.get('action')
                    v = l.get('value', 1)
                    try:
                        value = float(v) if v is not None else 0.0
                        if action in ['decrement', 'update']:
                            current -= value
                        elif action == 'increment':  # This handles rollbacks of decrements
                            current += value
                    except Exception:
                        continue
            return max(0, current)  # Don't go below 0
            
        elif task_type == 'percentage':
            # Find the latest percentage value, only allowing increases
            latest_value = 0.0
            for l in self._data.get('logs', []):
                if l.get('goal_id') == goal_id and l.get('action') == 'update':
                    v = l.get('value', 0)
                    try:
                        # Only allow increases - ignore any value lower than current
                        new_value = float(v)
                        if new_value > latest_value:
                            latest_value = new_value
                    except Exception:
                        continue
            return min(100, latest_value)  # Cap at 100%
            
        return 0.0

    def goal_progress_status(self, goal_id: int, today: Optional[date] = None) -> dict:
        """Return progress summary for a goal.

        Returns a dict with keys: progress, target, percent, expected, in_track, task_type.
        If scheduling/target info is missing, percent/expected/in_track will be None.
        Pass `today` (datetime.date) for deterministic tests; otherwise uses date.today().
        """
        g = self.get_goal(goal_id)
        if g is None:
            return {}
        if today is None:
            today = date.today()

        task_type = g.get('task_type', 'increment')
        current_value = self._calculate_current_value(goal_id)
        target = g.get('target')

        res = {
            'progress': current_value, 
            'target': target, 
            'task_type': task_type,
            'percent': None, 
            'expected': None, 
            'in_track': None
        }

        if target is not None and target != 0:
            if task_type == 'increment':
                percent = float(current_value) / float(target) if target else None
                res['percent'] = percent
            elif task_type == 'decrement':
                # For decrement, progress is how much we've reduced from target
                reduced = float(target) - current_value
                percent = reduced / float(target) if target else None
                res['percent'] = percent
                res['progress'] = reduced  # Show reduction as progress
            elif task_type == 'percentage':
                percent = current_value / 100.0  # current_value is already 0-100
                res['percent'] = percent

            # Calculate expected progress for time-based goals
            if g.get('start_date') and g.get('end_date'):
                try:
                    start = date.fromisoformat(g['start_date'])
                    end = date.fromisoformat(g['end_date'])
                    
                    total_days = (end - start).days + 1
                    if total_days <= 0:
                        total_days = 1

                    if today < start:
                        elapsed = 0
                    elif today > end:
                        elapsed = total_days
                    else:
                        elapsed = (today - start).days + 1

                    if task_type == 'increment':
                        expected = float(target) * (elapsed / total_days)
                        in_track = current_value + 1e-9 >= expected
                    elif task_type == 'decrement':
                        expected_reduced = float(target) * (elapsed / total_days)
                        expected_remaining = float(target) - expected_reduced
                        in_track = current_value <= expected_remaining + 1e-9
                        res['expected'] = expected_reduced  # Show expected reduction
                    elif task_type == 'percentage':
                        expected = 100 * (elapsed / total_days)
                        in_track = current_value + 1e-9 >= expected
                        res['expected'] = expected

                    if task_type != 'decrement':
                        res['expected'] = expected if task_type != 'percentage' else expected
                    res['in_track'] = in_track
                    
                except Exception:
                    pass

        return res

    def add_log(self, goal_id: int, action: str, value=None, ts=None):
        lid = self._next_id('log')
        entry = {'id': lid, 'goal_id': goal_id, 'action': action, 'value': value, 'ts': ts}
        self._data.setdefault('logs', []).append(entry)
        self._save()
        return entry

    def list_logs(self):
        return list(self._data.get('logs', []))

    def get_logs_for_goal(self, goal_id: int):
        """Get all logs for a specific goal, with timestamp field added."""
        # First check if the goal exists
        goal = self.get_goal(goal_id)
        if goal is None:
            return None
        
        # Filter logs by goal_id and add timestamp field
        logs = []
        for log in self._data.get('logs', []):
            if log.get('goal_id') == goal_id:
                # Create a copy and add timestamp field
                log_copy = log.copy()
                log_copy['timestamp'] = log.get('ts', '')  # Use 'ts' field as 'timestamp'
                logs.append(log_copy)
        
        return logs

    def edit_log(self, log_id: int, **fields):
        """Edit a log entry by id. Fields can include action, value, ts."""
        for l in self._data.setdefault('logs', []):
            if l.get('id') == log_id:
                for k, v in fields.items():
                    if k in ('action', 'value', 'ts'):
                        l[k] = v
                self._save()
                return l
        return None

    def delete_log(self, log_id: int) -> bool:
        logs = self._data.get('logs', [])
        for i, l in enumerate(logs):
            if l.get('id') == log_id:
                del logs[i]
                self._save()
                return True
        return False

    def delete_goal(self, goal_id: int, user_id: int = None) -> bool:
        goals = self._data.get('goals', [])
        for i, g in enumerate(goals):
            if g.get('id') == goal_id:
                if user_id is not None and g.get('user_id') != user_id:
                    return False  # User doesn't own this goal
                del goals[i]
                self._save()
                return True
        return False

    def update_goal_value(self, goal_id: int, action: str, value: float = 1, ts: str = None, user_id: int = None):
        """Update goal value based on task type.
        
        action can be: 'increment', 'decrement', 'update' (for percentage)
        """
        goal = self.get_goal(goal_id, user_id)
        if not goal:
            return None
            
        task_type = goal.get('task_type', 'increment')
        
        # Validate action matches task type
        if task_type == 'increment' and action not in ['increment', 'update']:
            action = 'increment'
        elif task_type == 'decrement' and action not in ['decrement', 'update']:
            action = 'decrement'
        elif task_type == 'percentage' and action != 'update':
            action = 'update'
        
        # For percentage tasks, enforce no-decrease rule for manual updates only
        # (rollbacks work by deleting entries, not creating new ones)
        if task_type == 'percentage' and action == 'update':
            current_value = self._calculate_current_value(goal_id)
            if value < current_value:  # Changed <= to < to allow setting same value
                # Don't create a log entry if the new value is lower
                return None
        
        lid = self._next_id('log')
        entry = {
            'id': lid, 
            'goal_id': goal_id, 
            'action': action, 
            'value': value, 
            'ts': ts or date.today().isoformat()
        }
        self._data.setdefault('logs', []).append(entry)
        self._save()
        return entry

    def rollback_log(self, log_id: int):
        """Create reverse operations for audit trail, then delete the specified log entry and all subsequent entries for the same goal"""
        # Find the log to rollback
        original_log = None
        logs = self._data.get('logs', [])
        
        for log in logs:
            if log.get('id') == log_id:
                original_log = log
                break
        
        if not original_log:
            return None
        
        goal_id = original_log.get('goal_id')
        
        # Only rollback the specific log entry that was clicked
        logs_to_rollback = [original_log]
        
        # Simply delete the original log entry - no reverse operations needed
        logs_to_delete_ids = [log.get('id') for log in logs_to_rollback]
        deleted_count = 0
        
        # Remove the original logs
        logs = self._data.get('logs', [])
        for log_id_to_delete in logs_to_delete_ids:
            for i, log in enumerate(logs):
                if log.get('id') == log_id_to_delete:
                    del logs[i]
                    deleted_count += 1
                    break
        
        self._save()
        
        # Return info about what was done
        return {
            'deleted_count': deleted_count,
            'deleted_log_ids': logs_to_delete_ids,
            'goal_id': goal_id
        }

    # User management methods
    def create_user(self, name: str, email: str, password_hash: str):
        """Create a new user account"""
        user_id = self._next_id('user')
        user = {
            'id': user_id,
            'name': name,
            'email': email,
            'password_hash': password_hash,
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        self._data.setdefault('users', []).append(user)
        self._save()
        return user

    def get_user_by_email(self, email: str):
        """Get user by email address"""
        for user in self._data.get('users', []):
            if user.get('email') == email:
                return user
        return None

    def get_user_by_id(self, user_id: int):
        """Get user by ID"""
        for user in self._data.get('users', []):
            if user.get('id') == user_id:
                return user
        return None
