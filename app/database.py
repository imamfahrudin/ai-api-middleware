import os
import logging
import sqlite3
import threading
import datetime
import json
import time

class KeyManager:
    """A thread-safe class to manage API keys with advanced, historical tracking and self-healing capabilities."""
    def __init__(self, db_path='data/keys.db'):
        self.db_path = db_path
        self.lock = threading.Lock()
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        # Add caching for expensive operations
        self._cache = {}
        self._cache_ttl = 10  # 10 second TTL
        self._initialize_db()
        self._migrate_from_env()
        self.ensure_default_settings()

    def _get_cached(self, key, compute_func, *args, **kwargs):
        """Get cached result or compute and cache it."""
        now = time.time()
        if key in self._cache:
            cached_time, cached_result = self._cache[key]
            if now - cached_time < self._cache_ttl:
                return cached_result
        
        result = compute_func(*args, **kwargs)
        self._cache[key] = (now, result)
        return result

    def _invalidate_cache(self, key_prefix=None):
        """Invalidate cache entries, optionally by prefix."""
        if key_prefix:
            keys_to_remove = [k for k in self._cache.keys() if k.startswith(key_prefix)]
            for k in keys_to_remove:
                del self._cache[k]
        else:
            self._cache.clear()

    def _initialize_db(self):
        with self.lock:
            cursor = self.conn.cursor()
            
            # --- Create 'keys' table if it doesn't exist ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS keys (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL DEFAULT 'Unnamed',
                    key_value TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL DEFAULT 'Healthy',
                    disabled_until TEXT DEFAULT NULL,
                    note TEXT,
                    last_rotated_at TEXT NOT NULL DEFAULT '1970-01-01T00:00:00Z'
                )
            """)

            # --- Safely Upgrade 'keys' table ---
            cursor.execute("PRAGMA table_info(keys)")
            columns = [info[1] for info in cursor.fetchall()]
            if 'note' not in columns:
                cursor.execute("ALTER TABLE keys ADD COLUMN note TEXT")
            if 'last_rotated_at' not in columns:
                cursor.execute("ALTER TABLE keys ADD COLUMN last_rotated_at TEXT NOT NULL DEFAULT '1970-01-01T00:00:00Z'")
            if 'key_type' in columns:
                logging.info("Old 'key_type' column found. It is no longer used.")


            # --- Create 'daily_stats' table if it doesn't exist ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, key_id INTEGER NOT NULL, date TEXT NOT NULL,
                    requests INTEGER NOT NULL DEFAULT 0, successes INTEGER NOT NULL DEFAULT 0, errors INTEGER NOT NULL DEFAULT 0,
                    tokens_in INTEGER NOT NULL DEFAULT 0, tokens_out INTEGER NOT NULL DEFAULT 0, total_latency_ms INTEGER NOT NULL DEFAULT 0,
                    error_codes TEXT NOT NULL DEFAULT '{}', model_usage TEXT NOT NULL DEFAULT '{}',
                    FOREIGN KEY (key_id) REFERENCES keys (id) ON DELETE CASCADE, UNIQUE (key_id, date)
                )
            """)
            
            # --- Safely Upgrade 'daily_stats' table ---
            cursor.execute("PRAGMA table_info(daily_stats)")
            daily_stats_columns = [info[1] for info in cursor.fetchall()]
            if 'error_codes' not in daily_stats_columns:
                cursor.execute("ALTER TABLE daily_stats ADD COLUMN error_codes TEXT NOT NULL DEFAULT '{}'")
            if 'model_usage' not in daily_stats_columns:
                cursor.execute("ALTER TABLE daily_stats ADD COLUMN model_usage TEXT NOT NULL DEFAULT '{}'")

            # --- Create 'settings' table for configuration ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Note: Default settings are handled by ensure_default_settings() method
            # This ensures consistency between initialization and runtime checks

            self.conn.commit()

    def _migrate_from_env(self):
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM keys")
            if cursor.fetchone()[0] > 0: return

            all_keys = set()
            gemini_keys_str = os.environ.get('GEMINI_API_KEYS')
            if gemini_keys_str:
                all_keys.update([key.strip() for key in gemini_keys_str.split(',') if key.strip()])
            
            if all_keys:
                logging.info(f"Performing one-time migration of {len(all_keys)} keys from environment variables...")
                for key in all_keys:
                    try: 
                        cursor.execute("INSERT INTO keys (key_value) VALUES (?)", (key,))
                    except sqlite3.IntegrityError: pass
                self.conn.commit()

    def get_all_keys_from_db(self):
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT id, name, key_value, status FROM keys ORDER BY id")
            return [dict(row) for row in cursor.fetchall()]

    def get_all_keys_with_kpi(self):
        """Calculates a Key Performance Index (KPI) for each key."""
        return self._get_cached('keys_with_kpi', self._compute_keys_with_kpi)

    def _compute_keys_with_kpi(self):
        """Internal method to compute keys with KPI (cached)."""
        keys = self.get_all_keys_from_db()
        today_str = datetime.date.today().isoformat()
        
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT key_id, successes, requests, total_latency_ms FROM daily_stats WHERE date = ?", (today_str,))
            today_stats = {row['key_id']: row for row in cursor.fetchall()}

        for key in keys:
            stats = today_stats.get(key['id'])
            if not stats or stats['requests'] == 0:
                key['kpi'] = 100
                continue
            
            success_rate = (stats['successes'] / stats['requests'])
            avg_latency_ms = stats['total_latency_ms'] / stats['requests']
            latency_score = max(0, 1 - (avg_latency_ms / 5000))

            key['kpi'] = int((success_rate * 70) + (latency_score * 30))
        return keys

    def add_key(self, key_value, name=None, note=None):
        if not key_value or len(key_value) < 10: return False, "Invalid key."
        key_name = name.strip() if name and name.strip() else 'Unnamed'
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("INSERT INTO keys (key_value, name, note) VALUES (?, ?, ?)", (key_value, key_name, note))
                self.conn.commit()
                self._invalidate_cache()  # Invalidate cache after adding key
                return True, "Key added."
            except sqlite3.IntegrityError: return False, "Key exists."

    def update_key(self, key_id, new_name=None, new_value=None, new_status=None, new_note=None):
        with self.lock:
            updates, params = [], []
            if new_name is not None:
                updates.append("name = ?")
                params.append(new_name.strip() if new_name.strip() else 'Unnamed')
            if new_value and len(new_value) > 10:
                updates.append("key_value = ?")
                params.append(new_value)
            if new_status and new_status in ['Healthy', 'Disabled']:
                 updates.append("status = ?")
                 updates.append("disabled_until = NULL")
                 params.append(new_status)
            if new_note is not None:
                updates.append("note = ?")
                params.append(new_note)

            if not updates: return False, "No valid data."
            params.append(key_id)
            try:
                cursor = self.conn.cursor()
                cursor.execute(f"UPDATE keys SET {', '.join(updates)} WHERE id = ?", tuple(params))
                self.conn.commit()
                self._invalidate_cache()  # Invalidate cache after updating key
                return True, "Key updated."
            except sqlite3.IntegrityError: return False, "Update failed."

    def remove_key(self, key_id):
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM keys WHERE id = ?", (key_id,))
            self.conn.commit()
            self._invalidate_cache()  # Invalidate cache after removing key
            return cursor.rowcount > 0

    def bulk_update_status(self, key_ids, status):
        if not key_ids or status not in ['Healthy', 'Disabled', 'Resting']:
            return False, "Invalid data for bulk update."
        with self.lock:
            try:
                cursor = self.conn.cursor()
                placeholders = ', '.join('?' for _ in key_ids)
                if status == 'Resting':
                    rest_until = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=3600)).isoformat()
                    cursor.execute(f"UPDATE keys SET status = ?, disabled_until = ? WHERE id IN ({placeholders})", (status, rest_until, *key_ids))
                else:
                    cursor.execute(f"UPDATE keys SET status = ?, disabled_until = NULL WHERE id IN ({placeholders})", (status, *key_ids))
                self.conn.commit()
                self._invalidate_cache()  # Invalidate cache after bulk update
                return True, f"{cursor.rowcount} keys updated to {status}."
            except sqlite3.Error as e:
                return False, f"Database error: {e}"

    def get_key_details(self, key_id):
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT id, name, key_value, status, note FROM keys WHERE id = ?", (key_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_all_keys_for_export(self):
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT name, key_value, note FROM keys ORDER BY id")
            return [dict(row) for row in cursor.fetchall()]

    def bulk_import_keys(self, keys_data):
        if not isinstance(keys_data, list):
            return 0, 0, "Invalid data format: expected a list of keys."

        with self.lock:
            imported_count = 0
            skipped_count = 0
            cursor = self.conn.cursor()
            for key_obj in keys_data:
                key_value = key_obj.get('key_value')
                name = key_obj.get('name', 'Unnamed')
                note = key_obj.get('note')

                if not key_value or len(key_value) < 10:
                    skipped_count += 1
                    continue

                try:
                    cursor.execute("INSERT INTO keys (key_value, name, note) VALUES (?, ?, ?)", (key_value, name, note))
                    imported_count += 1
                except sqlite3.IntegrityError:
                    skipped_count += 1
            self.conn.commit()
            self._invalidate_cache()  # Invalidate cache after bulk import
        return imported_count, skipped_count, "Import complete."


    def get_daily_stats(self, key_id, days=30):
        with self.lock:
            cursor = self.conn.cursor()
            date_limit = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
            cursor.execute("SELECT * FROM daily_stats WHERE key_id = ? AND date >= ? ORDER BY date ASC", (key_id, date_limit))
            return [dict(row) for row in cursor.fetchall()]

    def get_global_stats(self, days=7):
        return self._get_cached('global_stats', self._compute_global_stats, days)

    def _compute_global_stats(self, days=7):
        """Internal method to compute global stats (cached)."""
        with self.lock:
            cursor = self.conn.cursor()
            date_limit = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
            today_str = datetime.date.today().isoformat()
            
            cursor.execute("SELECT date, SUM(requests) as total_requests, SUM(successes) as total_successes, SUM(total_latency_ms) as total_latency, SUM(tokens_in) as total_tokens_in, SUM(tokens_out) as total_tokens_out FROM daily_stats WHERE date >= ? GROUP BY date ORDER BY date ASC", (date_limit,))
            historical_data = [dict(row) for row in cursor.fetchall()]

            cursor.execute("SELECT status, COUNT(*) as count FROM keys GROUP BY status")
            health_status = {row['status']: row['count'] for row in cursor.fetchall()}
            
            # New logic for stacked bar chart data
            cursor.execute("SELECT k.name, ds.model_usage FROM daily_stats ds JOIN keys k ON ds.key_id = k.id WHERE ds.date = ?", (today_str,))
            request_distribution = []
            for row in cursor.fetchall():
                request_distribution.append({
                    "name": row['name'],
                    "usage": json.loads(row['model_usage'])
                })

            error_codes_today, model_usage_today = {}, {}
            cursor.execute("SELECT error_codes, model_usage FROM daily_stats WHERE date = ?", (today_str,))
            for row in cursor.fetchall():
                for code, count in json.loads(row['error_codes']).items():
                    error_codes_today[code] = error_codes_today.get(code, 0) + count
                for model, count in json.loads(row['model_usage']).items():
                    model_usage_today[model] = model_usage_today.get(model, 0) + count
            
            if 'unknown' in model_usage_today:
                del model_usage_today['unknown']
            
            return {"historical": historical_data, "health_status": health_status, "error_codes_today": error_codes_today, "request_distribution": request_distribution, "model_usage_today": model_usage_today}

    def get_next_key(self, exclude_ids=None):
        """Get the next healthy key, optionally excluding certain key IDs (for failover)."""
        with self.lock:
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            cursor = self.conn.cursor()

            # Heal any resting keys whose time is up
            cursor.execute("UPDATE keys SET status='Healthy', disabled_until=NULL WHERE status='Resting' AND disabled_until < ?", (now_iso,))
            self.conn.commit()

            # Select the least recently used key for rotation, excluding already tried keys
            if exclude_ids:
                placeholders = ','.join('?' for _ in exclude_ids)
                cursor.execute(f"SELECT * FROM keys WHERE status = 'Healthy' AND id NOT IN ({placeholders}) ORDER BY last_rotated_at ASC LIMIT 1", exclude_ids)
            else:
                cursor.execute("SELECT * FROM keys WHERE status = 'Healthy' ORDER BY last_rotated_at ASC LIMIT 1")
            
            key_info = cursor.fetchone()

            if not key_info:
                return None
            
            # Immediately mark this key as "used" for rotation purposes
            cursor.execute("UPDATE keys SET last_rotated_at = ? WHERE id = ?", (now_iso, key_info['id']))
            self.conn.commit()
            
            return dict(key_info)

    def update_key_stats(self, key_id, success, model_name, error_code=None, tokens_in=0, tokens_out=0, latency_ms=0):
        with self.lock:
            now = datetime.datetime.now(datetime.timezone.utc)
            today_str = now.date().isoformat()
            
            cursor = self.conn.cursor()
            status_update_sql, status_params = "", []
            if success and error_code is None:
                cursor.execute("SELECT status FROM keys WHERE id=?",(key_id,))
                if cursor.fetchone()['status'] == 'Resting': 
                    status_update_sql = "status = 'Healthy', disabled_until = NULL"
            elif error_code == 429:
                rest_until = (now + datetime.timedelta(seconds=60)).isoformat()
                status_update_sql, status_params = "status = 'Resting', disabled_until = ?", [rest_until]
            elif error_code in [400, 401, 403]:
                status_update_sql = "status = 'Disabled', disabled_until = NULL"
            if status_update_sql:
                status_params.append(key_id)
                cursor.execute(f"UPDATE keys SET {status_update_sql} WHERE id = ?", tuple(status_params))
            
            cursor.execute("INSERT OR IGNORE INTO daily_stats (key_id, date) VALUES (?, ?)", (key_id, today_str))
            cursor.execute("SELECT error_codes, model_usage FROM daily_stats WHERE key_id = ? AND date = ?", (key_id, today_str))
            row = cursor.fetchone()
            error_codes = json.loads(row['error_codes'])
            model_usage = json.loads(row['model_usage'])

            update_fields = "requests = requests + 1, total_latency_ms = total_latency_ms + ?"
            update_params = [latency_ms]
            if success:
                update_fields += ", successes = successes + 1, tokens_in = tokens_in + ?, tokens_out = tokens_out + ?"
                update_params.extend([tokens_in, tokens_out])
                model_usage[model_name] = model_usage.get(model_name, 0) + 1
                update_fields += ", model_usage = ?"
                update_params.append(json.dumps(model_usage))
            else:
                update_fields += ", errors = errors + 1"
                if error_code:
                    error_codes[str(error_code)] = error_codes.get(str(error_code), 0) + 1
                    update_fields += ", error_codes = ?"
                    update_params.append(json.dumps(error_codes))

            update_params.extend([key_id, today_str])
            cursor.execute(f"UPDATE daily_stats SET {update_fields} WHERE key_id = ? AND date = ?", tuple(update_params))
            self.conn.commit()

    # Settings management methods
    def get_setting(self, key, default=None):
        """Get a setting value from the database."""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row['value'] if row else default

    def set_setting(self, key, value):
        """Set a setting value in the database."""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO settings (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
            """, (key, str(value)))
            self.conn.commit()

    def get_all_settings(self):
        """Get all settings as a dictionary."""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT key, value FROM settings")
            settings = {}
            for row in cursor.fetchall():
                try:
                    # Convert string values to appropriate types
                    value = row['value']
                    if value is None:
                        continue
                    elif value.lower() in ('true', 'false'):
                        settings[row['key']] = value.lower() == 'true'
                    elif value.lstrip('-').isdigit():
                        settings[row['key']] = int(value)
                    else:
                        settings[row['key']] = value
                except (AttributeError, ValueError) as e:
                    # Skip corrupted settings and log warning
                    import logging
                    logging.warning(f"Skipping corrupted setting {row['key']}: {value} - {e}")
                    continue
            return settings

    def update_settings(self, settings_dict):
        """Update multiple settings at once."""
        with self.lock:
            cursor = self.conn.cursor()
            for key, value in settings_dict.items():
                cursor.execute("""
                    INSERT INTO settings (key, value, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = CURRENT_TIMESTAMP
                """, (key, str(value)))
            self.conn.commit()

    def ensure_default_settings(self):
        """Ensure all required default settings exist in the database."""
        default_settings = {
            # Performance Settings
            'streaming_enabled': 'true',
            'connection_pooling_enabled': 'true',
            'model_cache_enabled': 'true',
            'max_retries': '7',
            'request_timeout': '30',
            'connect_timeout': '10',
            'read_timeout': '60',
            'streaming_timeout': '120',

            # Connection & Retry Settings
            'retry_total': '7',
            'retry_backoff_factor': '0.1',
            'pool_connections': '20',
            'pool_maxsize': '100',
            'max_stream_retries': '2',
            'chunk_retry_delay': '1.0',

            # Cache Settings
            'cache_timeout': '300',
            'model_cache_timeout': '10',

            # Buffer Optimization Settings
            'small_request_threshold': '1024',
            'large_request_threshold': '100000',
            'small_buffer_size': '4096',
            'large_buffer_size': '16384',
            'min_buffer_size': '1024',
            'max_buffer_size': '65536',
            'json_buffer_limit': '2048',

            # Logging & Monitoring Settings
            'enable_request_logging': 'true',
            'log_level': 'INFO',
            'enable_metrics_collection': 'true',
            'enable_performance_logging': 'true',
            'log_request_body': 'false',
            'log_response_body': 'false',

            # Rate Limiting Settings
            'enable_rate_limiting': 'false',
            'requests_per_minute': '60',
            'rate_limiting_strategy': 'sliding_window',
            'burst_allowance': '10',

            # Security Settings
            'enable_cors': 'true',
            'cors_origins': '*',
            'enable_request_validation': 'false',
            'max_request_size': '10485760',
            'blocked_user_agents': '',

            # Advanced Proxy Settings
            'enable_health_checks': 'true',
            'health_check_interval': '300',
            'failover_strategy': 'round_robin',
            'enable_circuit_breaker': 'false',
            'circuit_breaker_threshold': '5',
            'enable_request_id_injection': 'true',

            # Performance Fine-tuning
            'buffer_size': '8192',
            'max_concurrent_requests': '100',
            'keepalive_timeout': '30',
            'enable_graceful_shutdown': 'true',
            'cache_max_age': '300'
        }

        with self.lock:
            cursor = self.conn.cursor()
            for key, default_value in default_settings.items():
                cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
                row = cursor.fetchone()
                if not row:
                    # Insert missing default setting
                    cursor.execute("""
                        INSERT INTO settings (key, value, updated_at)
                        VALUES (?, ?, CURRENT_TIMESTAMP)
                    """, (key, default_value))
            self.conn.commit()
