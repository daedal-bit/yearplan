from pathlib import Path
import json
from datetime import date, datetime, timedelta
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
            with open(self.path, 'r', encoding='utf-8') as fh:
                self._data = json.load(fh)
        except Exception:
            self._data = {'goals': []}

    def _save(self):
        try:
            with open(self.path, 'w', encoding='utf-8') as fh:
                json.dump(self._data, fh, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def add_goal(self, text: str, user_id: int = None):
        # kept for backward-compat: simple add_goal(text)
        gid = self._next_id('goal')
        self._data['goals'].append({'id': gid, 'text': text, 'created_at': None, 'user_id': user_id})
        self._save()
        return gid

    def add_goal_with_meta(self, text: str, start_date: Optional[str] = None, end_date: Optional[str] = None, target: Optional[float] = None, task_type: str = 'increment', user_id: int = None, start_value: Optional[float] = None):
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
            'start_value': start_value,
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
        for u in self._data.get('users', []):
            if isinstance(u.get('id'), int) and u['id'] > max_id:
                max_id = u['id']
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
            # Start at baseline (start_value if provided, else target), subtract decrements, add increments
            try:
                baseline = float(goal.get('start_value')) if goal.get('start_value') is not None else float(target or 0)
            except Exception:
                baseline = float(target or 0)
            current = baseline
            for l in self._data.get('logs', []):
                if l.get('goal_id') == goal_id:
                    action = l.get('action')
                    v = l.get('value', 1)
                    try:
                        value = float(v) if v is not None else 0.0
                        if action == 'decrement':
                            current -= value
                        elif action == 'increment':
                            current += value
                        elif action == 'update':
                            current = value
                    except Exception:
                        continue
            return max(0, current)  # Don't go below 0
            
        elif task_type == 'percentage':
            # For percentage tasks, find the most recent update value
            latest_value = 0.0
            latest_ts = None
            
            for l in self._data.get('logs', []):
                if l.get('goal_id') == goal_id and l.get('action') == 'update':
                    ts = l.get('ts')
                    if latest_ts is None or (ts and ts > latest_ts):
                        latest_ts = ts
                        try:
                            latest_value = float(l.get('value', 0))
                        except Exception:
                            pass
            
            return min(100, max(0, latest_value))  # Clamp between 0-100
        
        return 0.0

    def goal_progress_status(self, goal_id: int):
        """Calculate goal progress and status"""
        goal = self.get_goal(goal_id)
        if not goal:
            return None

        current_value = self._calculate_current_value(goal_id)
        task_type = goal.get('task_type', 'increment')
        target = goal.get('target')
        start_date = goal.get('start_date')
        end_date = goal.get('end_date')
        # Start baseline:
        # 1) If goal has explicit start_value, use it
        # 2) Else for decrement use target (typical baseline), else 0
        try:
            if 'start_value' in goal and goal.get('start_value') is not None:
                start_baseline = float(goal.get('start_value'))
            elif task_type == 'decrement':
                start_baseline = float(target or 0)
            else:
                start_baseline = 0.0
        except Exception:
            start_baseline = 0.0

        # Clamp current within [min(start, target), max(start, target)] for non-percentage goals
        clamped_current = current_value
        try:
            if task_type != 'percentage' and target is not None:
                t = float(target)
                s = float(start_baseline)
                lo = min(s, t)
                hi = max(s, t)
                clamped_current = max(lo, min(hi, float(current_value)))
        except Exception:
            pass

        # Calculate progress percentage using absolute goal distance = |target - start|
        progress_pct = 0.0
        if task_type == 'percentage':
            progress_pct = current_value
        else:
            try:
                if target is not None:
                    total_distance = abs(float(target) - float(start_baseline))
                    if total_distance > 0:
                        # distance achieved relative to baseline (symmetric)
                        achieved = abs(float(clamped_current) - float(start_baseline))
                        progress_pct = max(0.0, min(100.0, (achieved / total_distance) * 100.0))
                    else:
                        progress_pct = 100.0 if float(clamped_current) == float(target) else 0.0
                else:
                    progress_pct = 0.0
            except Exception:
                progress_pct = 0.0

        # Calculate expected progress based on dates (inclusive day counting)
        expected = None
        in_track = True
        if start_date and end_date:
            try:
                start = datetime.fromisoformat(start_date).date()
                end = datetime.fromisoformat(end_date).date()
                today = date.today()

                total_days_inclusive = (end - start).days + 1
                if total_days_inclusive <= 0:
                    total_days_inclusive = 1

                if today < start:
                    time_progress = 0.0
                elif today > end:
                    time_progress = 1.0
                else:
                    elapsed_inclusive = (today - start).days + 1
                    if elapsed_inclusive < 0:
                        elapsed_inclusive = 0
                    if elapsed_inclusive > total_days_inclusive:
                        elapsed_inclusive = total_days_inclusive
                    time_progress = elapsed_inclusive / total_days_inclusive

                if task_type == 'percentage':
                    expected = 100 * time_progress
                else:
                    # expected value along the path from start_baseline to target
                    try:
                        t = float(target or 0.0)
                        s = float(start_baseline)
                        expected = s + (t - s) * time_progress
                    except Exception:
                        expected = (target or 0)

                # Determine if in track (only when expected non-zero)
                try:
                    if expected not in (None, 0):
                        # Compare achieved distance vs expected distance from baseline
                        try:
                            s = float(start_baseline)
                            exp_dist = abs(float(expected) - s)
                            cur_dist = abs(float(clamped_current) - s)
                            ratio = (cur_dist / exp_dist) if exp_dist not in (None, 0) else 1.0
                        except Exception:
                            ratio = 1.0
                        in_track = 0.7 <= ratio <= 1.3
                except Exception:
                    pass
            except Exception:
                pass

        return {
            'progress': clamped_current,
            'percent': min(100, max(0, progress_pct)),
            'target': target,
            'start': start_baseline,
            'expected': expected,
            'in_track': in_track,
            'task_type': task_type
        }

    def add_log(self, goal_id: int, action: str, value=None, ts=None):
        lid = self._next_id('log')
        entry = {'id': lid, 'goal_id': goal_id, 'action': action, 'value': value, 'ts': ts}
        self._data.setdefault('logs', []).append(entry)
        self._save()
        return entry

    def list_logs(self):
        return list(self._data.get('logs', []))

    def mark_goal_completed(self, goal_id: int, user_id: int = None):
        """Mark a goal as completed and set completed_at timestamp."""
        for g in self._data.get('goals', []):
            if g.get('id') == goal_id:
                if user_id is not None and g.get('user_id') != user_id:
                    return False
                g['is_completed'] = True
                try:
                    g['completed_value'] = float(self._calculate_current_value(goal_id))
                except Exception:
                    g['completed_value'] = g.get('target')
                try:
                    g['completed_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                except Exception:
                    g['completed_at'] = date.today().isoformat()
                self._save()
                return True
        return False

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
        logs = self._data.setdefault('logs', [])
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

    def set_goal_field(self, goal_id: int, field: str, value, user_id: int = None) -> bool:
        """Set an arbitrary field on a goal with optional user ownership check."""
        try:
            for g in self._data.get('goals', []):
                if g.get('id') == goal_id:
                    if user_id is not None and g.get('user_id') != user_id:
                        return False
                    g[field] = value
                    self._save()
                    return True
        except Exception:
            return False
        return False

    def update_goal_name(self, goal_id: int, new_text: str, user_id: int = None) -> bool:
        """Update the display text/name of a goal."""
        if not new_text:
            return False
        for g in self._data.get('goals', []):
            if g.get('id') == goal_id:
                if user_id is not None and g.get('user_id') != user_id:
                    return False
                g['text'] = str(new_text)
                self._save()
                return True
        return False

    def update_goal_target(self, goal_id: int, new_target, user_id: int = None) -> bool:
        """Update the target value for a goal. Does not modify logs or current value."""
        try:
            goals = self._data.get('goals', [])
            for g in goals:
                if g.get('id') == goal_id:
                    if user_id is not None and g.get('user_id') != user_id:
                        return False
                    # Coerce numeric target or set None
                    if new_target is None or new_target == "":
                        g['target'] = None
                    else:
                        g['target'] = float(new_target)
                    self._save()
                    return True
        except Exception:
            return False
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
        # Append log first so current reflects this update
        self._data.setdefault('logs', []).append(entry)

        # Auto-adjust target based on new current value and task type
        try:
            new_current = self._calculate_current_value(goal_id)
            tgt = goal.get('target')
            if tgt is not None:
                if task_type == 'decrement':
                    # If we've gone below the target, move target down to current
                    if float(new_current) < float(tgt):
                        goal['target'] = float(new_current)
                elif task_type == 'increment':
                    # If we've exceeded the target, move target up to current
                    if float(new_current) > float(tgt):
                        goal['target'] = float(new_current)
            # Mark completed if percent >= 100
            status = self.goal_progress_status(goal_id)
            if status and status.get('percent', 0) >= 100:
                self.mark_goal_completed(goal_id, user_id)
        except Exception:
            pass

        self._save()
        return entry

    def rollback_log(self, log_id: int):
        """Delete the specified log entry and all subsequent entries for the same goal"""
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
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'reminder_frequency': 'weekly',  # Default to weekly reminders
            'reminder_enabled': True,
            'last_reminder_sent': None
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

    def user_owns_log(self, log_id: int, user_id: int) -> bool:
        """Check if user owns the goal that this log belongs to"""
        # Find the log
        for log in self._data.get('logs', []):
            if log.get('id') == log_id:
                goal_id = log.get('goal_id')
                if goal_id:
                    goal = self.get_goal(goal_id, user_id)
                    return goal is not None
                return False
        return False

    def update_user_password(self, user_id: int, new_password_hash: str) -> bool:
        """Update user password"""
        users = self._data.get('users', [])
        for user in users:
            if user.get('id') == user_id:
                user['password_hash'] = new_password_hash
                self._save()
                return True
        return False

    def update_user_email(self, user_id: int, new_email: str) -> bool:
        """Update user email"""
        users = self._data.get('users', [])
        for user in users:
            if user.get('id') == user_id:
                user['email'] = new_email
                self._save()
                return True
        return False

    def delete_user(self, user_id: int) -> bool:
        """Delete user and all associated data"""
        try:
            # Remove all user's goals
            goals = self._data.get('goals', [])
            self._data['goals'] = [g for g in goals if g.get('user_id') != user_id]
            
            # Remove all logs associated with user's goals
            # First get list of goal IDs that belonged to this user
            user_goal_ids = [g.get('id') for g in goals if g.get('user_id') == user_id]
            
            # Remove logs for those goals
            logs = self._data.get('logs', [])
            self._data['logs'] = [l for l in logs if l.get('goal_id') not in user_goal_ids]
            
            # Remove the user
            users = self._data.get('users', [])
            self._data['users'] = [u for u in users if u.get('id') != user_id]
            
            self._save()
            return True
        except Exception:
            return False

    def create_unverified_user(self, name: str, email: str, password_hash: str, verification_token: str):
        """Create a new unverified user account"""
        user_id = self._next_id('user')
        user = {
            'id': user_id,
            'name': name,
            'email': email,
            'password_hash': password_hash,
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'is_verified': False,
            'verification_token': verification_token,
            'token_expires': (datetime.now() + timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S'),
            'reminder_frequency': 'weekly',  # Default to weekly reminders
            'reminder_enabled': True,
            'last_reminder_sent': None
        }
        
        self._data.setdefault('users', []).append(user)
        self._save()
        return user

    def verify_user_email(self, token: str) -> bool:
        """Verify user email with token"""
        users = self._data.get('users', [])
        for user in users:
            if (user.get('verification_token') == token and 
                not user.get('is_verified', False)):
                
                # Check if token is expired
                token_expires = user.get('token_expires')
                if token_expires:
                    expires_dt = datetime.strptime(token_expires, '%Y-%m-%d %H:%M:%S')
                    if datetime.now() > expires_dt:
                        return False  # Token expired
                
                # Verify the user
                user['is_verified'] = True
                user.pop('verification_token', None)
                user.pop('token_expires', None)
                self._save()
                return True
        return False

    def get_user_by_token(self, token: str):
        """Get user by verification token"""
        for user in self._data.get('users', []):
            if user.get('verification_token') == token:
                return user
        return None

    def update_user_reminder_preferences(self, user_id: int, frequency: str, enabled: bool = True):
        """Update user's reminder preferences"""
        for user in self._data.get('users', []):
            if user.get('id') == user_id:
                user['reminder_frequency'] = frequency
                user['reminder_enabled'] = enabled
                self._save()
                return True
        return False

    def get_user_reminder_preferences(self, user_id: int):
        """Get user's reminder preferences"""
        for user in self._data.get('users', []):
            if user.get('id') == user_id:
                return {
                    'frequency': user.get('reminder_frequency', 'weekly'),
                    'enabled': user.get('reminder_enabled', True),
                    'last_sent': user.get('last_reminder_sent')
                }
        return None

    def update_last_reminder_sent(self, user_id: int, timestamp: str = None):
        """Update when the last reminder was sent to user"""
        if timestamp is None:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        for user in self._data.get('users', []):
            if user.get('id') == user_id:
                user['last_reminder_sent'] = timestamp
                self._save()
                return True
        return False

    def get_users_needing_reminders(self):
        """Get all users who need reminders based on their preferences and last reminder sent"""
        users_needing_reminders = []
        now = datetime.now()
        
        for user in self._data.get('users', []):
            # Skip if reminders disabled or user not verified
            if not user.get('reminder_enabled', True) or not user.get('is_verified', True):
                continue
            
            frequency = user.get('reminder_frequency', 'weekly')
            last_sent = user.get('last_reminder_sent')
            
            # If never sent a reminder, send one
            if not last_sent:
                users_needing_reminders.append(user)
                continue
            
            # Parse last sent timestamp
            try:
                last_sent_dt = datetime.strptime(last_sent, '%Y-%m-%d %H:%M:%S')
            except (ValueError, TypeError):
                # Invalid timestamp, send reminder
                users_needing_reminders.append(user)
                continue
            
            # Calculate if reminder is due based on frequency
            time_since_last = now - last_sent_dt
            
            should_send = False
            if frequency == 'daily' and time_since_last >= timedelta(days=1):
                should_send = True
            elif frequency == 'weekly' and time_since_last >= timedelta(days=7):
                should_send = True
            elif frequency == 'biweekly' and time_since_last >= timedelta(days=14):
                should_send = True
            elif frequency == 'monthly' and time_since_last >= timedelta(days=30):
                should_send = True
            
            if should_send:
                users_needing_reminders.append(user)
        
        return users_needing_reminders
        return None

    def is_user_verified(self, user_id: int) -> bool:
        """Check if user is verified"""
        user = self.get_user_by_id(user_id)
        return user.get('is_verified', False) if user else False