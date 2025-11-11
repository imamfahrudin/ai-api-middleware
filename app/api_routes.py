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
            'streaming_enabled': bool,
            'connection_pooling_enabled': bool,
            'model_cache_enabled': bool,
            'max_retries': int,
            'request_timeout': int
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
