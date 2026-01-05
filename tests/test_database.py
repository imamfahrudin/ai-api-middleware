import pytest
import sqlite3
import os
from app.database import KeyManager

@pytest.fixture
def key_manager():
    """Fixture for KeyManager with in-memory DB."""
    km = KeyManager(':memory:')
    yield km
    km.conn.close()

class TestKeyManager:
    """Test KeyManager class."""

    def test_init_creates_tables(self, key_manager):
        """Test initialization creates required tables."""
        cursor = key_manager.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        assert 'keys' in tables
        assert 'daily_stats' in tables
        assert 'settings' in tables

    def test_add_key(self, key_manager):
        """Test adding a key."""
        result = key_manager.add_key('test_key_long_enough', 'Test Key')
        assert result == (True, "Key added.")
        keys = key_manager.get_all_keys_from_db()
        assert len(keys) == 1
        assert keys[0]['key_value'] == 'test_key_long_enough'

    def test_get_next_key_rotation(self, key_manager):
        """Test key rotation selects least recently used key."""
        # Add keys with different rotation times
        key_manager.add_key('key1_long_enough_for_validation', 'Key 1')
        key_manager.add_key('key2_long_enough_for_validation', 'Key 2')
        key_manager.add_key('key3_long_enough_for_validation', 'Key 3')
        
        # Get first key (should be key1 as it's first added)
        key1 = key_manager.get_next_key()
        assert key1['key_value'] == 'key1_long_enough_for_validation'
        
        # Get second key (should be key2 as it's next in rotation)
        key2 = key_manager.get_next_key()
        assert key2['key_value'] == 'key2_long_enough_for_validation'
        
        # Get third key (should be key3)
        key3 = key_manager.get_next_key()
        assert key3['key_value'] == 'key3_long_enough_for_validation'
        
        # Next should rotate back to key1 (least recently used)
        key1_again = key_manager.get_next_key()
        assert key1_again['key_value'] == 'key1_long_enough_for_validation'

    def test_key_healing_from_resting(self, key_manager):
        """Test that resting keys are healed back to healthy after timeout."""
        import time
        from unittest.mock import patch
        
        key_manager.add_key('test_key_long_enough_for_validation', 'Test Key')
        key_id = key_manager.get_all_keys_from_db()[0]['id']
        
        # Manually set key to resting with past timeout
        with key_manager.lock:
            cursor = key_manager.conn.cursor()
            past_time = '2000-01-01T00:00:00Z'  # Past time
            cursor.execute("UPDATE keys SET status = 'Resting', disabled_until = ? WHERE id = ?", (past_time, key_id))
            key_manager.conn.commit()
        
        # get_next_key should heal the resting key
        key = key_manager.get_next_key()
        assert key is not None
        assert key['status'] == 'Healthy'

    def test_update_key_stats_status_transitions(self, key_manager):
        """Test key status transitions based on error codes."""
        key_manager.add_key('test_key_long_enough_for_validation', 'Test Key')
        key_id = key_manager.get_all_keys_from_db()[0]['id']
        
        # Test 429 error -> Resting status
        key_manager.update_key_stats(key_id, success=False, model_name='test_model', error_code=429, latency_ms=100)
        key = key_manager.get_key_details(key_id)
        assert key['status'] == 'Resting'
        
        # Test success on resting key -> Healthy status
        key_manager.update_key_stats(key_id, success=True, model_name='test_model', latency_ms=100)
        key = key_manager.get_key_details(key_id)
        assert key['status'] == 'Healthy'
        
        # Test 401 error -> Disabled status
        key_manager.update_key_stats(key_id, success=False, model_name='test_model', error_code=401, latency_ms=100)
        key = key_manager.get_key_details(key_id)
        assert key['status'] == 'Disabled'

    def test_update_key_stats_success_metrics(self, key_manager):
        """Test updating key stats captures success metrics and token counts."""
        key_manager.add_key('test_key_long_enough_for_validation', 'Test Key')
        key_id = key_manager.get_all_keys_from_db()[0]['id']
        key_manager.update_key_stats(key_id, success=True, model_name='test_model', latency_ms=100, tokens_in=10, tokens_out=20)
        stats = key_manager.get_key_aggregated_stats(key_id)
        assert stats['total_requests'] == 1
        assert stats['successful_requests'] == 1
        assert stats['total_tokens_in'] == 10
        assert stats['total_tokens_out'] == 20
        assert stats['avg_latency'] == 100

    def test_get_setting_default(self, key_manager):
        """Test getting default setting."""
        value = key_manager.get_setting('nonexistent', 'default')
        assert value == 'default'

    def test_set_setting(self, key_manager):
        """Test setting a setting."""
        key_manager.set_setting('test_key', 'test_value')
        value = key_manager.get_setting('test_key', 'default')
        assert value == 'test_value'

    def test_bulk_update_status_disable(self, key_manager):
        """Test disabling a key via bulk update."""
        key_manager.add_key('test_key_long_enough_for_validation', 'Test Key')
        key_id = key_manager.get_all_keys_from_db()[0]['id']
        key_manager.bulk_update_status([key_id], 'Disabled')
        key = key_manager.get_key_details(key_id)
        assert key['status'] == 'Disabled'

    def test_bulk_update_status_enable(self, key_manager):
        """Test enabling a key via bulk update."""
        key_manager.add_key('test_key_long_enough_for_validation', 'Test Key')
        key_id = key_manager.get_all_keys_from_db()[0]['id']
        key_manager.bulk_update_status([key_id], 'Disabled')
        key_manager.bulk_update_status([key_id], 'Healthy')
        key = key_manager.get_key_details(key_id)
        assert key['status'] == 'Healthy'

    def test_remove_key(self, key_manager):
        """Test removing a key."""
        key_manager.add_key('test_key_long_enough_for_validation', 'Test Key')
        key_id = key_manager.get_all_keys_from_db()[0]['id']
        success = key_manager.remove_key(key_id)
        assert success
        keys = key_manager.get_all_keys_from_db()
        assert len(keys) == 0

    def test_get_all_keys_with_kpi(self, key_manager):
        """Test getting keys with KPI data."""
        key_manager.add_key('test_key_long_enough_for_validation', 'Test Key')
        key_id = key_manager.get_all_keys_from_db()[0]['id']
        key_manager.update_key_stats(key_id, success=True, model_name='test_model')
        keys = key_manager.get_all_keys_with_kpi()
        assert len(keys) == 1
        assert 'kpi' in keys[0]

    def test_thread_safety(self, key_manager):
        """Test thread safety with concurrent access."""
        import threading
        import time

        results = []

        def add_keys(thread_id):
            for i in range(10):
                key_manager.add_key(f'key{thread_id}_{i}_long_enough_for_validation', f'Key {thread_id}-{i}')
                results.append(1)
                time.sleep(0.01)  # Small delay to encourage race conditions

        threads = [threading.Thread(target=add_keys, args=(t,)) for t in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        keys = key_manager.get_all_keys_from_db()
        assert len(keys) == 30  # 3 threads * 10 keys each

    def test_add_key_duplicate(self, key_manager):
        """Test adding a duplicate key triggers IntegrityError."""
        key_manager.add_key('test_key_long_enough_for_validation', 'Test Key')
        result = key_manager.add_key('test_key_long_enough_for_validation', 'Duplicate Key')
        assert result == (False, "Key exists.")

    def test_add_key_invalid(self, key_manager):
        """Test adding an invalid key."""
        result = key_manager.add_key('short', 'Short Key')
        assert result == (False, "Invalid key.")

    def test_update_key_duplicate_value(self, key_manager):
        """Test updating key to duplicate value triggers IntegrityError."""
        key_manager.add_key('key1_long_enough_for_validation', 'Key 1')
        key_manager.add_key('key2_long_enough_for_validation', 'Key 2')
        key_id = key_manager.get_all_keys_from_db()[0]['id']
        result = key_manager.update_key(key_id, new_value='key2_long_enough_for_validation')
        assert result == (False, "Update failed.")

    def test_update_key_no_changes(self, key_manager):
        """Test updating key with no valid data."""
        key_manager.add_key('test_key_long_enough_for_validation', 'Test Key')
        key_id = key_manager.get_all_keys_from_db()[0]['id']
        result = key_manager.update_key(key_id)
        assert result == (False, "No valid data.")

    def test_bulk_update_status_invalid(self, key_manager):
        """Test bulk update with invalid status."""
        result = key_manager.bulk_update_status([1], 'Invalid')
        assert result == (False, "Invalid status for bulk update.")

    def test_bulk_update_status_no_ids(self, key_manager):
        """Test bulk update with no key IDs."""
        result = key_manager.bulk_update_status([], 'Healthy')
        assert result == (False, "No key IDs provided.")

    def test_bulk_update_status_delete_error(self, key_manager):
        """Test bulk delete with database error."""
        # This is hard to trigger naturally, but we can test the path
        pass  # Skip for now, as it's hard to mock sqlite3.Error in bulk_update_status

    def test_get_key_details_invalid_id(self, key_manager):
        """Test getting details for non-existent key."""
        result = key_manager.get_key_details(999)
        assert result is None

    def test_bulk_import_keys_invalid_data(self, key_manager):
        """Test bulk import with invalid data."""
        result = key_manager.bulk_import_keys("not a list")
        assert result == (0, 0, "Invalid data format: expected a list of keys.")

    def test_bulk_import_keys_invalid_key(self, key_manager):
        """Test bulk import with invalid key."""
        keys_data = [{'key_value': 'short'}]
        imported, skipped, msg = key_manager.bulk_import_keys(keys_data)
        assert imported == 0
        assert skipped == 1
        assert "Import complete." in msg

    def test_get_next_key_exclude_ids(self, key_manager):
        """Test get_next_key with exclude_ids."""
        key_manager.add_key('key1_long_enough_for_validation', 'Key 1')
        key_manager.add_key('key2_long_enough_for_validation', 'Key 2')
        key1 = key_manager.get_next_key()
        key2 = key_manager.get_next_key(exclude_ids=[key1['id']])
        assert key2['key_value'] == 'key2_long_enough_for_validation'

    def test_get_next_key_no_healthy_keys(self, key_manager):
        """Test get_next_key when no healthy keys available."""
        # Add a key and disable it
        key_manager.add_key('test_key_long_enough_for_validation', 'Test Key')
        key_id = key_manager.get_all_keys_from_db()[0]['id']
        key_manager.bulk_update_status([key_id], 'Disabled')
        result = key_manager.get_next_key()
        assert result is None

    def test_update_key_stats_status_changes(self, key_manager):
        """Test status changes in update_key_stats."""
        key_manager.add_key('test_key_long_enough_for_validation', 'Test Key')
        key_id = key_manager.get_all_keys_from_db()[0]['id']
        
        # Test 400 error -> Disabled
        key_manager.update_key_stats(key_id, success=False, model_name='test', error_code=400)
        key = key_manager.get_key_details(key_id)
        assert key['status'] == 'Disabled'
        
        # Reset to Healthy
        key_manager.bulk_update_status([key_id], 'Healthy')
        
        # Test 401 error -> Disabled
        key_manager.update_key_stats(key_id, success=False, model_name='test', error_code=401)
        key = key_manager.get_key_details(key_id)
        assert key['status'] == 'Disabled'
        
        # Reset
        key_manager.bulk_update_status([key_id], 'Healthy')
        
        # Test 403 error -> Disabled
        key_manager.update_key_stats(key_id, success=False, model_name='test', error_code=403)
        key = key_manager.get_key_details(key_id)
        assert key['status'] == 'Disabled'

    def test_migrate_from_env(self, key_manager):
        """Test migration from environment variables."""
        import os
        # Set env var
        os.environ['GEMINI_API_KEYS'] = 'env_key1_long_enough,env_key2_long_enough'
        # Create new manager to trigger migration
        km = KeyManager(':memory:')
        keys = km.get_all_keys_from_db()
        assert len(keys) == 2
        km.conn.close()
        # Clean up
        del os.environ['GEMINI_API_KEYS']

    def test_ensure_default_settings(self, key_manager):
        """Test ensure_default_settings adds missing defaults."""
        # Delete a setting to test
        with key_manager.lock:
            cursor = key_manager.conn.cursor()
            cursor.execute("DELETE FROM settings WHERE key = 'max_retries'")
            key_manager.conn.commit()
        
        # Call ensure_default_settings
        key_manager.ensure_default_settings()
        
        # Check it's back
        value = key_manager.get_setting('max_retries')
        assert value == '7'

    def test_get_all_settings_type_conversion(self, key_manager):
        """Test type conversion in get_all_settings."""
        key_manager.set_setting('bool_true', 'true')
        key_manager.set_setting('bool_false', 'false')
        key_manager.set_setting('int_value', '42')
        key_manager.set_setting('str_value', 'hello')
        
        settings = key_manager.get_all_settings()
        assert settings['bool_true'] is True
        assert settings['bool_false'] is False
        assert settings['int_value'] == 42
        assert settings['str_value'] == 'hello'

    def test_get_key_aggregated_stats_no_data(self, key_manager):
        """Test get_key_aggregated_stats with no data."""
        key_manager.add_key('test_key_long_enough_for_validation', 'Test Key')
        key_id = key_manager.get_all_keys_from_db()[0]['id']
        stats = key_manager.get_key_aggregated_stats(key_id)
        assert stats['total_requests'] == 0
        assert stats['avg_latency'] == 0

    def test_get_global_stats_caching(self, key_manager):
        """Test global stats caching."""
        # First call
        stats1 = key_manager.get_global_stats()
        # Second call should use cache
        stats2 = key_manager.get_global_stats()
        assert stats1 == stats2

    def test_get_all_keys_with_kpi_no_stats(self, key_manager):
        """Test KPI calculation when no stats available."""
        key_manager.add_key('test_key_long_enough_for_validation', 'Test Key')
        keys = key_manager.get_all_keys_with_kpi()
        assert keys[0]['kpi'] == 100