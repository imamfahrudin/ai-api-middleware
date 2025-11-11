import time
import json
import requests
from flask import jsonify, request, Blueprint
from flasgger import swag_from
from app.auth import login_required
from app.database import KeyManager
from app.logging_utils import live_log

api_bp = Blueprint('api', __name__)
key_manager = KeyManager()

@api_bp.route('/middleware/api/keys', methods=['GET'])
@login_required
def get_keys():
    """
    Get all API keys with KPI data
    ---
    tags:
      - API Keys
    security:
      - SessionAuth: []
    responses:
      200:
        description: List of all API keys with their statistics
        schema:
          type: array
          items:
            type: object
            properties:
              id:
                type: integer
              name:
                type: string
              key_value:
                type: string
              status:
                type: string
              total_requests:
                type: integer
              successful_requests:
                type: integer
              failed_requests:
                type: integer
      302:
        description: Redirect to login if not authenticated
    """
    return jsonify(key_manager.get_all_keys_with_kpi())

@api_bp.route('/middleware/api/logs', methods=['GET'])
@login_required
def get_logs():
    """
    Get live logs
    ---
    tags:
      - Logs
    security:
      - SessionAuth: []
    responses:
      200:
        description: List of live log entries
        schema:
          type: array
          items:
            type: object
      302:
        description: Redirect to login if not authenticated
    """
    return jsonify(list(live_log))
    
@api_bp.route('/middleware/api/keys/<int:key_id>', methods=['GET'])
@login_required
def get_key_details_route(key_id):
    """
    Get detailed information about a specific API key
    ---
    tags:
      - API Keys
    security:
      - SessionAuth: []
    parameters:
      - name: key_id
        in: path
        type: integer
        required: true
        description: ID of the key to retrieve
    responses:
      200:
        description: Key details retrieved successfully
        schema:
          type: object
          properties:
            id:
              type: integer
            name:
              type: string
            key_value:
              type: string
            status:
              type: string
            note:
              type: string
            total_requests:
              type: integer
            successful_requests:
              type: integer
            failed_requests:
              type: integer
      404:
        description: Key not found
      302:
        description: Redirect to login if not authenticated
    """
    details = key_manager.get_key_details(key_id)
    return jsonify(details) if details else (jsonify({"error": "Key not found"}), 404)

@api_bp.route('/middleware/api/keys/<int:key_id>/stats', methods=['GET'])
@login_required
def get_stats_route(key_id):
    """
    Get daily statistics for a specific API key
    ---
    tags:
      - Statistics
    security:
      - SessionAuth: []
    parameters:
      - name: key_id
        in: path
        type: integer
        required: true
        description: ID of the key
    responses:
      200:
        description: Daily statistics retrieved successfully
        schema:
          type: array
          items:
            type: object
            properties:
              date:
                type: string
              requests:
                type: integer
              tokens_in:
                type: integer
              tokens_out:
                type: integer
      302:
        description: Redirect to login if not authenticated
    """
    return jsonify(key_manager.get_daily_stats(key_id))

@api_bp.route('/middleware/api/global-stats', methods=['GET'])
@login_required
def get_global_stats_route():
    """
    Get global statistics across all API keys
    ---
    tags:
      - Statistics
    security:
      - SessionAuth: []
    responses:
      200:
        description: Global statistics retrieved successfully
        schema:
          type: object
          properties:
            total_requests:
              type: integer
            successful_requests:
              type: integer
            failed_requests:
              type: integer
            total_tokens_in:
              type: integer
            total_tokens_out:
              type: integer
            total_keys:
              type: integer
            active_keys:
              type: integer
      302:
        description: Redirect to login if not authenticated
    """
    return jsonify(key_manager.get_global_stats())

@api_bp.route('/middleware/api/keys', methods=['POST'])
@login_required
def add_key_route():
    """
    Add a new API key
    ---
    tags:
      - API Keys
    security:
      - SessionAuth: []
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - key
            - name
          properties:
            key:
              type: string
              description: The API key value
            name:
              type: string
              description: Name for the API key
            note:
              type: string
              description: Optional note about the key
    responses:
      201:
        description: Key added successfully
      400:
        description: Failed to add key
      302:
        description: Redirect to login if not authenticated
    """
    data = request.get_json()
    success, msg = key_manager.add_key(data.get('key'), data.get('name'), data.get('note'))
    return jsonify({"success": success, "message": msg}), 201 if success else 400

@api_bp.route('/middleware/api/keys/bulk-action', methods=['POST'])
@login_required
def bulk_action_route():
    """
    Bulk update status for multiple API keys
    ---
    tags:
      - API Keys
    security:
      - SessionAuth: []
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - key_ids
            - status
          properties:
            key_ids:
              type: array
              items:
                type: integer
              description: Array of key IDs to update
            status:
              type: string
              enum: [active, inactive, error]
              description: New status for the keys
    responses:
      200:
        description: Keys updated successfully
      400:
        description: Failed to update keys
      302:
        description: Redirect to login if not authenticated
    """
    data = request.get_json()
    key_ids = data.get('key_ids', [])
    status = data.get('status')
    success, msg = key_manager.bulk_update_status(key_ids, status)
    return jsonify({"success": success, "message": msg}), 200 if success else 400

@api_bp.route('/middleware/api/keys/<int:key_id>', methods=['PUT'])
@login_required
def update_key_route(key_id):
    """
    Update an existing API key
    ---
    tags:
      - API Keys
    security:
      - SessionAuth: []
    parameters:
      - name: key_id
        in: path
        type: integer
        required: true
        description: ID of the key to update
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            name:
              type: string
            key:
              type: string
            status:
              type: string
              enum: [active, inactive, error]
            note:
              type: string
    responses:
      200:
        description: Key updated successfully
      400:
        description: Failed to update key
      302:
        description: Redirect to login if not authenticated
    """
    data = request.get_json()
    success, msg = key_manager.update_key(key_id, new_name=data.get('name'), new_value=data.get('key'), new_status=data.get('status'), new_note=data.get('note'))
    return jsonify({"success": success, "message": msg}), 200 if success else 400

@api_bp.route('/middleware/api/keys/<int:key_id>', methods=['DELETE'])
@login_required
def remove_key_route(key_id):
    """
    Delete an API key
    ---
    tags:
      - API Keys
    security:
      - SessionAuth: []
    parameters:
      - name: key_id
        in: path
        type: integer
        required: true
        description: ID of the key to delete
    responses:
      200:
        description: Key deleted successfully
      404:
        description: Key not found
      302:
        description: Redirect to login if not authenticated
    """
    success = key_manager.remove_key(key_id)
    return jsonify({"success": success}), 200 if success else 404

@api_bp.route('/middleware/api/keys/export', methods=['GET'])
@login_required
def export_keys_route():
    """
    Export all API keys in a portable format
    ---
    tags:
      - API Keys
    security:
      - SessionAuth: []
    responses:
      200:
        description: Keys exported successfully
        schema:
          type: array
          items:
            type: object
            properties:
              name:
                type: string
              key:
                type: string
              note:
                type: string
              status:
                type: string
      302:
        description: Redirect to login if not authenticated
    """
    keys = key_manager.get_all_keys_for_export()
    return jsonify(keys)

@api_bp.route('/middleware/api/keys/import', methods=['POST'])
@login_required
def import_keys_route():
    """
    Import API keys in bulk from exported format
    ---
    tags:
      - API Keys
    security:
      - SessionAuth: []
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: array
          items:
            type: object
            required:
              - name
              - key
            properties:
              name:
                type: string
                description: Name for the API key
              key:
                type: string
                description: The API key value
              note:
                type: string
                description: Optional note
              status:
                type: string
                description: Key status (active/inactive)
    responses:
      200:
        description: Keys imported successfully
        schema:
          type: object
          properties:
            success:
              type: boolean
            message:
              type: string
      302:
        description: Redirect to login if not authenticated
    """
    data = request.get_json()
    imported, skipped, message = key_manager.bulk_import_keys(data)
    return jsonify({"success": True, "message": f"{message} Imported {imported}, skipped {skipped}."})

@api_bp.route('/middleware/api/settings', methods=['GET'])
@login_required
def get_settings():
    """
    Get all current settings
    ---
    tags:
      - Settings
    security:
      - SessionAuth: []
    responses:
      200:
        description: Current settings values
        schema:
          type: object
          properties:
            streaming_enabled:
              type: boolean
            connection_pooling_enabled:
              type: boolean
            model_cache_enabled:
              type: boolean
            max_retries:
              type: integer
            request_timeout:
              type: integer
      302:
        description: Redirect to login if not authenticated
    """
    settings = key_manager.get_all_settings()
    return jsonify(settings)

@api_bp.route('/middleware/api/settings', methods=['POST'])
@login_required
def update_settings():
    """
    Update settings
    ---
    tags:
      - Settings
    security:
      - SessionAuth: []
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            streaming_enabled:
              type: boolean
            connection_pooling_enabled:
              type: boolean
            model_cache_enabled:
              type: boolean
            max_retries:
              type: integer
              minimum: 1
              maximum: 20
            request_timeout:
              type: integer
              minimum: 5
              maximum: 300
    responses:
      200:
        description: Settings updated successfully
        schema:
          type: object
          properties:
            success:
              type: boolean
            message:
              type: string
      400:
        description: Invalid settings provided
      302:
        description: Redirect to login if not authenticated
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "No settings data provided"}), 400

        # Validate settings
        valid_settings = {
            # Performance Settings
            'streaming_enabled': bool,
            'connection_pooling_enabled': bool,
            'model_cache_enabled': bool,
            'max_retries': int,
            'request_timeout': int,

            # Logging & Monitoring Settings
            'enable_request_logging': bool,
            'log_level': str,
            'enable_metrics_collection': bool,
            'enable_performance_logging': bool,
            'log_request_body': bool,
            'log_response_body': bool,

            # Rate Limiting Settings
            'enable_rate_limiting': bool,
            'requests_per_minute': int,
            'rate_limiting_strategy': str,
            'burst_allowance': int,

            # Security Settings
            'enable_cors': bool,
            'cors_origins': str,
            'enable_request_validation': bool,
            'max_request_size': int,
            'blocked_user_agents': str,

            # Advanced Proxy Settings
            'enable_health_checks': bool,
            'health_check_interval': int,
            'failover_strategy': str,
            'enable_circuit_breaker': bool,
            'circuit_breaker_threshold': int,
            'enable_request_id_injection': bool,

            # Performance Fine-tuning
            'buffer_size': int,
            'max_concurrent_requests': int,
            'keepalive_timeout': int,
            'enable_graceful_shutdown': bool,
            'cache_max_age': int
        }

        validated_settings = {}
        for key, value in data.items():
            if key in valid_settings:
                expected_type = valid_settings[key]
                if not isinstance(value, expected_type):
                    try:
                        value = expected_type(value)
                    except (ValueError, TypeError):
                        return jsonify({"success": False, "message": f"Invalid value for {key}: expected {expected_type.__name__}"}), 400

                # Additional validation for numeric values
                if key == 'max_retries' and not (1 <= value <= 20):
                    return jsonify({"success": False, "message": "max_retries must be between 1 and 20"}), 400
                elif key == 'request_timeout' and not (5 <= value <= 300):
                    return jsonify({"success": False, "message": "request_timeout must be between 5 and 300 seconds"}), 400
                elif key == 'requests_per_minute' and not (1 <= value <= 1000):
                    return jsonify({"success": False, "message": "requests_per_minute must be between 1 and 1000"}), 400
                elif key == 'burst_allowance' and not (0 <= value <= 100):
                    return jsonify({"success": False, "message": "burst_allowance must be between 0 and 100"}), 400
                elif key == 'max_request_size' and not (1024 <= value <= 104857600):
                    return jsonify({"success": False, "message": "max_request_size must be between 1KB and 100MB"}), 400
                elif key == 'health_check_interval' and not (60 <= value <= 3600):
                    return jsonify({"success": False, "message": "health_check_interval must be between 60 and 3600 seconds"}), 400
                elif key == 'circuit_breaker_threshold' and not (1 <= value <= 50):
                    return jsonify({"success": False, "message": "circuit_breaker_threshold must be between 1 and 50"}), 400
                elif key == 'buffer_size' and not (1024 <= value <= 65536):
                    return jsonify({"success": False, "message": "buffer_size must be between 1KB and 64KB"}), 400
                elif key == 'max_concurrent_requests' and not (1 <= value <= 1000):
                    return jsonify({"success": False, "message": "max_concurrent_requests must be between 1 and 1000"}), 400
                elif key == 'keepalive_timeout' and not (5 <= value <= 300):
                    return jsonify({"success": False, "message": "keepalive_timeout must be between 5 and 300 seconds"}), 400
                elif key == 'cache_max_age' and not (0 <= value <= 3600):
                    return jsonify({"success": False, "message": "cache_max_age must be between 0 and 3600 seconds"}), 400

            # Validation for string values
            if key == 'log_level' and value not in ['DEBUG', 'INFO', 'WARNING', 'ERROR']:
                return jsonify({"success": False, "message": "log_level must be one of: DEBUG, INFO, WARNING, ERROR"}), 400
            elif key == 'rate_limiting_strategy' and value not in ['fixed_window', 'sliding_window', 'token_bucket']:
                return jsonify({"success": False, "message": "rate_limiting_strategy must be one of: fixed_window, sliding_window, token_bucket"}), 400
            elif key == 'failover_strategy' and value not in ['round_robin', 'random', 'least_used', 'priority']:
                return jsonify({"success": False, "message": "failover_strategy must be one of: round_robin, random, least_used, priority"}), 400

            validated_settings[key] = value

        key_manager.update_settings(validated_settings)
        return jsonify({"success": True, "message": "Settings updated successfully"})

    except Exception as e:
        return jsonify({"success": False, "message": f"Error updating settings: {str(e)}"}), 500

@api_bp.route('/middleware/api/settings/<setting_key>', methods=['GET'])
@login_required
def get_setting(setting_key):
    """
    Get a specific setting value
    ---
    tags:
      - Settings
    security:
      - SessionAuth: []
    parameters:
      - name: setting_key
        in: path
        type: string
        required: true
        description: The setting key to retrieve
    responses:
      200:
        description: Setting value
        schema:
          type: object
          properties:
            key:
              type: string
            value:
              type: string
      404:
        description: Setting not found
      302:
        description: Redirect to login if not authenticated
    """
    value = key_manager.get_setting(setting_key)
    if value is None:
        return jsonify({"error": "Setting not found"}), 404
    return jsonify({"key": setting_key, "value": value})


# --- MCP Management API Endpoints ---

@api_bp.route('/middleware/api/mcp/servers', methods=['GET'])
@login_required
def get_mcp_servers():
    """
    Get all MCP servers
    ---
    tags:
      - MCP Management
    security:
      - SessionAuth: []
    parameters:
      - name: status
        in: query
        type: string
        required: false
        description: Filter by status (Active, Inactive, Error)
    responses:
      200:
        description: List of MCP servers
        schema:
          type: array
          items:
            type: object
            properties:
              id:
                type: integer
              name:
                type: string
              url:
                type: string
              status:
                type: string
              auth_type:
                type: string
      302:
        description: Redirect to login if not authenticated
    """
    status_filter = request.args.get('status')
    servers = key_manager.get_mcp_servers(status_filter=status_filter)
    return jsonify(servers)

@api_bp.route('/middleware/api/mcp/servers', methods=['POST'])
@login_required
def add_mcp_server():
    """
    Add a new MCP server
    ---
    tags:
      - MCP Management
    security:
      - SessionAuth: []
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - name
            - url
          properties:
            name:
              type: string
              description: Server name
            url:
              type: string
              description: Server URL
            auth_type:
              type: string
              enum: ['none', 'bearer', 'api_key', 'oauth']
              default: 'none'
            auth_credentials:
              type: object
              description: Authentication credentials
            status:
              type: string
              enum: ['Active', 'Inactive', 'Error']
              default: 'Active'
    responses:
      201:
        description: Server created successfully
        schema:
          type: object
          properties:
            id:
              type: integer
            message:
              type: string
      400:
        description: Bad request
      302:
        description: Redirect to login if not authenticated
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        required_fields = ['name', 'url']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400

        server_id = key_manager.add_mcp_server(
            name=data['name'],
            url=data['url'],
            auth_type=data.get('auth_type', 'none'),
            auth_credentials=data.get('auth_credentials'),
            status=data.get('status', 'Active')
        )

        return jsonify({
            "id": server_id,
            "message": "MCP server created successfully"
        }), 201

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Failed to create MCP server: {str(e)}"}), 500

@api_bp.route('/middleware/api/mcp/servers/<int:server_id>', methods=['PUT'])
@login_required
def update_mcp_server(server_id):
    """
    Update an MCP server
    ---
    tags:
      - MCP Management
    security:
      - SessionAuth: []
    parameters:
      - name: server_id
        in: path
        type: integer
        required: true
        description: Server ID
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            name:
              type: string
            url:
              type: string
            auth_type:
              type: string
            auth_credentials:
              type: object
            status:
              type: string
    responses:
      200:
        description: Server updated successfully
      404:
        description: Server not found
      302:
        description: Redirect to login if not authenticated
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        # Check if server exists
        server = key_manager.get_mcp_server(server_id)
        if not server:
            return jsonify({"error": "MCP server not found"}), 404

        # Update server
        key_manager.update_mcp_server(server_id, **data)

        return jsonify({"message": "MCP server updated successfully"})

    except Exception as e:
        return jsonify({"error": f"Failed to update MCP server: {str(e)}"}), 500

@api_bp.route('/middleware/api/mcp/servers/<int:server_id>', methods=['DELETE'])
@login_required
def delete_mcp_server(server_id):
    """
    Delete an MCP server
    ---
    tags:
      - MCP Management
    security:
      - SessionAuth: []
    parameters:
      - name: server_id
        in: path
        type: integer
        required: true
        description: Server ID
    responses:
      200:
        description: Server deleted successfully
      404:
        description: Server not found
      302:
        description: Redirect to login if not authenticated
    """
    try:
        # Check if server exists
        server = key_manager.get_mcp_server(server_id)
        if not server:
            return jsonify({"error": "MCP server not found"}), 404

        # Delete server
        key_manager.delete_mcp_server(server_id)

        return jsonify({"message": "MCP server deleted successfully"})

    except Exception as e:
        return jsonify({"error": f"Failed to delete MCP server: {str(e)}"}), 500

@api_bp.route('/middleware/api/mcp/servers/test', methods=['POST'])
@login_required
def test_mcp_server_connection():
    """
    Test connection to an MCP server (new server configuration)
    ---
    tags:
      - MCP Management
    security:
      - SessionAuth: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            name:
              type: string
              description: Server name
            url:
              type: string
              description: Server URL
            auth_type:
              type: string
              enum: [none, bearer, api_key, oauth]
              description: Authentication type
            auth_credentials:
              type: object
              description: Authentication credentials
            timeout:
              type: integer
              description: Connection timeout in seconds
    responses:
      200:
        description: Connection test successful
      400:
        description: Invalid request
      500:
        description: Connection test failed
      302:
        description: Redirect to login if not authenticated
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No request data provided"}), 400

        name = data.get('name')
        url = data.get('url')
        auth_type = data.get('auth_type', 'none')
        auth_credentials = data.get('auth_credentials', {})
        timeout = data.get('timeout', 30)

        if not name or not url:
            return jsonify({"error": "Server name and URL are required"}), 400

        # Test connection using simplified synchronous approach

        # Test the connection using synchronous HTTP approach for now
        # This is a simplified version that tests basic connectivity
        connection_successful = False
        server_info = {
            "name": name,
            "url": url,
            "auth_type": auth_type,
            "protocol": "WebSocket" if url.startswith('ws://') or url.startswith('wss://') else "HTTP"
        }

        try:
            # For HTTP URLs, test basic connectivity
            if not (url.startswith('ws://') or url.startswith('wss://')):
                headers = {}

                # Prepare authentication headers
                if auth_type == 'bearer' and auth_credentials.get('token'):
                    headers['Authorization'] = f"Bearer {auth_credentials['token']}"
                elif auth_type == 'api_key' and auth_credentials.get('key'):
                    key_header = auth_credentials.get('header', 'X-API-Key')
                    headers[key_header] = auth_credentials['key']

                # Test basic HTTP connectivity
                test_url = url.rstrip('/') + '/health' if not url.endswith('/mcp') else url
                response = requests.get(test_url, headers=headers, timeout=timeout)

                if response.status_code in [200, 404, 405]:  # 404/405 may mean server is up but no health endpoint
                    connection_successful = True
            else:
                # For WebSocket connections, we'll implement a basic test
                # For now, assume WebSocket connections work if the URL format is correct
                connection_successful = True
                server_info['note'] = "WebSocket connection validation not fully implemented"

        except Exception as e:
            connection_successful = False

        if connection_successful:
            # For now, return a successful connection response without tool discovery
            # Tool discovery will be implemented with proper async support later
            return jsonify({
                "success": True,
                "message": "Connection test successful",
                "server_info": server_info,
                "available_tools": [],
                "note": "Tool discovery requires full MCP client implementation"
            })
        else:
            return jsonify({
                "success": False,
                "error": "Connection failed - unable to establish connection"
            }), 400

    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Connection test failed: {str(e)}"
        }), 500

@api_bp.route('/middleware/api/mcp/servers/<int:server_id>/test', methods=['POST'])
@login_required
def test_existing_mcp_server(server_id):
    """
    Test connection to an existing MCP server
    ---
    tags:
      - MCP Management
    security:
      - SessionAuth: []
    parameters:
      - name: server_id
        in: path
        type: integer
        required: true
        description: Server ID
    responses:
      200:
        description: Connection test successful
      404:
        description: Server not found
      500:
        description: Connection test failed
      302:
        description: Redirect to login if not authenticated
    """
    try:
        # Get server details from database
        server = key_manager.get_mcp_server(server_id)
        if not server:
            return jsonify({"error": "MCP server not found"}), 404

        # Test connection using simplified synchronous approach

        # Test the connection using synchronous approach
        connection_successful = False
        server_info = {
            "name": server['name'],
            "url": server['url'],
            "auth_type": server['auth_type'],
            "protocol": "WebSocket" if server['url'].startswith('ws://') or server['url'].startswith('wss://') else "HTTP"
        }

        try:
            # For HTTP URLs, test basic connectivity
            if not (server['url'].startswith('ws://') or server['url'].startswith('wss://')):
                headers = {}

                # Prepare authentication headers
                if server['auth_type'] == 'bearer' and server.get('auth_credentials', {}).get('token'):
                    headers['Authorization'] = f"Bearer {server['auth_credentials']['token']}"
                elif server['auth_type'] == 'api_key' and server.get('auth_credentials', {}).get('key'):
                    key_header = server['auth_credentials'].get('header', 'X-API-Key')
                    headers[key_header] = server['auth_credentials']['key']

                # Test basic HTTP connectivity
                test_url = server['url'].rstrip('/') + '/health' if not server['url'].endswith('/mcp') else server['url']
                response = requests.get(test_url, headers=headers, timeout=server.get('timeout', 30))

                if response.status_code in [200, 404, 405]:  # 404/405 may mean server is up but no health endpoint
                    connection_successful = True
            else:
                # For WebSocket connections, assume they work if URL format is correct
                connection_successful = True
                server_info['note'] = "WebSocket connection validation not fully implemented"

        except Exception as e:
            connection_successful = False

        if connection_successful:
            # Update server status to Active (healthy)
            key_manager.update_mcp_server(server_id, status='Active')

            return jsonify({
                "success": True,
                "message": "Connection test successful",
                "server_info": server_info
            })
        else:
            # Update server status to Error
            key_manager.update_mcp_server(server_id, status='Error')

            return jsonify({
                "success": False,
                "error": "Connection failed - unable to establish connection"
            }), 400

    except Exception as e:
        # Update server status to Error
        try:
            key_manager.update_mcp_server(server_id, status='Error')
        except:
            pass

        return jsonify({
            "success": False,
            "error": f"Connection test failed: {str(e)}"
        }), 500

@api_bp.route('/middleware/api/mcp/tools', methods=['GET'])
@login_required
def get_mcp_tools():
    """
    Get MCP tools
    ---
    tags:
      - MCP Management
    security:
      - SessionAuth: []
    parameters:
      - name: server_id
        in: query
        type: integer
        required: false
        description: Filter by server ID
      - name: active_only
        in: query
        type: boolean
        required: false
        default: true
        description: Only show active tools
    responses:
      200:
        description: List of MCP tools
        schema:
          type: array
          items:
            type: object
      302:
        description: Redirect to login if not authenticated
    """
    server_id = request.args.get('server_id', type=int)
    active_only = request.args.get('active_only', 'true').lower() == 'true'

    tools = key_manager.get_mcp_tools(server_id=server_id, active_only=active_only)
    return jsonify(tools)

@api_bp.route('/middleware/api/mcp/stats', methods=['GET'])
@login_required
def get_mcp_statistics():
    """
    Get MCP usage statistics
    ---
    tags:
      - MCP Management
    security:
      - SessionAuth: []
    parameters:
      - name: days
        in: query
        type: integer
        required: false
        default: 7
        description: Number of days to include in statistics
      - name: server_id
        in: query
        type: integer
        required: false
        description: Filter by server ID
    responses:
      200:
        description: MCP usage statistics
        schema:
          type: object
      302:
        description: Redirect to login if not authenticated
    """
    try:
        days = request.args.get('days', 7, type=int)
        server_id = request.args.get('server_id', type=int)

        # Get usage statistics
        usage_stats = key_manager.get_mcp_usage_stats(server_id=server_id, days=days)

        # Get server information
        servers = key_manager.get_mcp_servers()
        active_servers = [s for s in servers if s['status'] == 'Active']

        # Get tool information
        tools = key_manager.get_mcp_tools()

        # Calculate additional statistics
        total_calls = sum(s.get('total_calls', 0) for s in usage_stats)
        successful_calls = sum(s.get('successful_calls', 0) for s in usage_stats)
        success_rate = (successful_calls / total_calls * 100) if total_calls > 0 else 0

        # Group tools by category
        tool_categories = {}
        for tool in tools:
            category = tool.get('category', 'general')
            tool_categories[category] = tool_categories.get(category, 0) + 1

        return jsonify({
            'summary': {
                'total_calls': total_calls,
                'successful_calls': successful_calls,
                'success_rate': round(success_rate, 2),
                'active_servers': len(active_servers),
                'total_tools': len(tools)
            },
            'tool_categories': tool_categories,
            'usage_by_day': usage_stats,
            'servers': servers
        })

    except Exception as e:
        return jsonify({"error": f"Failed to get MCP statistics: {str(e)}"}), 500

@api_bp.route('/middleware/api/mcp/health', methods=['GET'])
@login_required
def get_mcp_health():
    """
    Get MCP server health status
    ---
    tags:
      - MCP Management
    security:
      - SessionAuth: []
    responses:
      200:
        description: MCP server health status
        schema:
          type: object
      302:
        description: Redirect to login if not authenticated
    """
    try:
        from app.mcp_integration import get_mcp_integration
        mcp_integration = get_mcp_integration()

        if not mcp_integration:
            return jsonify({
                "enabled": False,
                "error": "MCP integration not available"
            })

        # Get health statistics
        stats = mcp_integration.get_statistics()

        # Get recent health checks from database
        servers = key_manager.get_mcp_servers(status_filter='Active')
        server_health = []

        for server in servers:
            # Get latest health check for this server
            health_history = key_manager.get_mcp_usage_stats(server_id=server['id'], days=1)
            # This is a simplified health check - in production, you'd have a dedicated health table
            server_health.append({
                'id': server['id'],
                'name': server['name'],
                'url': server['url'],
                'status': 'healthy' if mcp_integration.get_client_for_server(server['id']) else 'disconnected',
                'last_check': server.get('last_health_check')
            })

        return jsonify({
            "enabled": stats.get('enabled', False),
            "statistics": stats,
            "servers": server_health
        })

    except Exception as e:
        return jsonify({"error": f"Failed to get MCP health: {str(e)}"}), 500

@api_bp.route('/middleware/api/mcp/reload', methods=['POST'])
@login_required
def reload_mcp_configuration():
    """
    Reload MCP configuration
    ---
    tags:
      - MCP Management
    security:
      - SessionAuth: []
    responses:
      200:
        description: MCP configuration reloaded
      302:
        description: Redirect to login if not authenticated
    """
    try:
        from app.mcp_integration import get_mcp_integration
        mcp_integration = get_mcp_integration()

        if not mcp_integration:
            return jsonify({"error": "MCP integration not available"}), 404

        # Reload configuration
        mcp_integration.reload_configuration()

        return jsonify({"message": "MCP configuration reloaded successfully"})

    except Exception as e:
        return jsonify({"error": f"Failed to reload MCP configuration: {str(e)}"}), 500
