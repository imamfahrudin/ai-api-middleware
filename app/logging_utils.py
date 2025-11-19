import datetime
import json
import logging
from collections import deque

# --- In-Memory Log for Live Feed ---
live_log = deque(maxlen=50) # Store the last 50 log entries for the dashboard feed

def add_log_entry(msg, color_class="text-gray-400"):
    """Add a log entry to the live log feed"""
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    live_log.append({"time": timestamp, "msg": msg, "color": color_class})

def log_request(method, path, headers=None, body=None, request_id=None):
    """Log incoming request details"""
    logger = logging.getLogger(__name__)
    
    # Basic request info
    log_msg = f"{method} {path}"
    if request_id:
        log_msg += f" [ID: {request_id}]"
    
    # Add headers if logging is enabled
    if headers:
        # Filter sensitive headers
        filtered_headers = {k: v for k, v in headers.items()
                          if k.lower() not in ['authorization', 'x-goog-api-key']}
        if filtered_headers:
            log_msg += f" Headers: {json.dumps(filtered_headers)}"
    
    # Add body if logging is enabled
    if body:
        try:
            # Truncate body if too large
            body_str = json.dumps(body) if isinstance(body, dict) else str(body)
            if len(body_str) > 500:
                body_str = body_str[:500] + "...[truncated]"
            log_msg += f" Body: {body_str}"
        except (TypeError, ValueError):
            log_msg += f" Body: [binary data, {len(body) if body else 0} bytes]"
    
    logger.info(log_msg)
    add_log_entry(f"REQUEST: {log_msg}", "text-blue-400")

def log_response(status_code, headers=None, body=None, request_id=None, latency_ms=None):
    """Log outgoing response details"""
    logger = logging.getLogger(__name__)
    
    # Basic response info
    log_msg = f"Response {status_code}"
    if request_id:
        log_msg += f" [ID: {request_id}]"
    if latency_ms:
        log_msg += f" ({latency_ms}ms)"
    
    # Add headers if logging is enabled
    if headers:
        # Filter sensitive headers
        filtered_headers = {k: v for k, v in headers.items()
                          if k.lower() not in ['set-cookie', 'authorization']}
        if filtered_headers:
            log_msg += f" Headers: {json.dumps(filtered_headers)}"
    
    # Add body if logging is enabled
    if body:
        try:
            # Truncate body if too large
            body_str = json.dumps(body) if isinstance(body, dict) else str(body)
            if len(body_str) > 500:
                body_str = body_str[:500] + "...[truncated]"
            log_msg += f" Body: {body_str}"
        except (TypeError, ValueError):
            log_msg += f" Body: [binary data, {len(body) if body else 0} bytes]"
    
    logger.info(log_msg)
    
    # Color code based on status
    if 200 <= status_code < 300:
        color = "text-green-400"
    elif 300 <= status_code < 400:
        color = "text-yellow-400"
    else:
        color = "text-red-500"
    
    add_log_entry(f"RESPONSE: {log_msg}", color)

def log_performance(operation, duration_ms, details=None):
    """Log performance metrics"""
    logger = logging.getLogger(__name__)
    
    log_msg = f"PERF: {operation} took {duration_ms}ms"
    if details:
        log_msg += f" - {details}"
    
    logger.info(log_msg)
    
    # Color code based on performance
    if duration_ms < 100:
        color = "text-green-400"
    elif duration_ms < 500:
        color = "text-yellow-400"
    else:
        color = "text-red-500"
    
    add_log_entry(log_msg, color)
