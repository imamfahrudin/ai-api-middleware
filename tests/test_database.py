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