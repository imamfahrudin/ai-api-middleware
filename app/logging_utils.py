import datetime
from collections import deque

# --- In-Memory Log for Live Feed ---
live_log = deque(maxlen=50) # Store the last 50 log entries for the dashboard feed

def add_log_entry(msg, color_class="text-gray-400"):
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    live_log.append({"time": timestamp, "msg": msg, "color": color_class})
