import time
import json
import requests
from flask import request, jsonify, Response, Blueprint

from app.database import KeyManager
from app.logging_utils import add_log_entry

proxy_bp = Blueprint('proxy', __name__)
key_manager = KeyManager()

# Gemini-specific routes for Swagger documentation
@proxy_bp.route('/v1beta/models/<model_name>:generateContent', methods=['POST'])
@proxy_bp.route('/v1/models/<model_name>:generateContent', methods=['POST'])
def gemini_generate_content(model_name):
    """
    Gemini Generate Content API
    ---
    tags:
      - Gemini API
    parameters:
      - name: model_name
        in: path
        type: string
        required: true
        description: Model name (e.g., 'gemini-pro', 'gemini-1.5-flash', 'gemini-1.5-pro')
        default: gemini-pro
      - name: body
        in: body
        required: true
        description: Gemini API request body
        schema:
          type: object
          required:
            - contents
          properties:
            contents:
              type: array
              items:
                type: object
                properties:
                  parts:
                    type: array
                    items:
                      type: object
                      properties:
                        text:
                          type: string
                  role:
                    type: string
                    enum: [user, model]
            generationConfig:
              type: object
              properties:
                temperature:
                  type: number
                  minimum: 0
                  maximum: 2
                topP:
                  type: number
                topK:
                  type: integer
                maxOutputTokens:
                  type: integer
            safetySettings:
              type: array
              items:
                type: object
          example:
            contents:
              - parts:
                  - text: "Write a story about a magic backpack."
            generationConfig:
              temperature: 0.7
              maxOutputTokens: 2048
    responses:
      200:
        description: Successful generation
        schema:
          type: object
          properties:
            candidates:
              type: array
              items:
                type: object
            usageMetadata:
              type: object
              properties:
                promptTokenCount:
                  type: integer
                candidatesTokenCount:
                  type: integer
                totalTokenCount:
                  type: integer
      400:
        description: Bad request
      503:
        description: No healthy API keys available
    """
    return proxy(f'v1beta/models/{model_name}:generateContent')

@proxy_bp.route('/v1beta/models', methods=['GET'])
@proxy_bp.route('/v1/models', methods=['GET'])
def gemini_list_models():
    """
    List available Gemini models
    ---
    tags:
      - Gemini API
    responses:
      200:
        description: List of available models
        schema:
          type: object
          properties:
            models:
              type: array
              items:
                type: object
                properties:
                  name:
                    type: string
                  displayName:
                    type: string
                  description:
                    type: string
      503:
        description: No healthy API keys available
    """
    return proxy('v1beta/models')

@proxy_bp.route('/v1beta/models/<model_name>:streamGenerateContent', methods=['POST'])
@proxy_bp.route('/v1/models/<model_name>:streamGenerateContent', methods=['POST'])
def gemini_stream_generate_content(model_name):
    """
    Gemini Streaming Generate Content API
    ---
    tags:
      - Gemini API
    parameters:
      - name: model_name
        in: path
        type: string
        required: true
        description: Model name (e.g., 'gemini-pro', 'gemini-1.5-flash')
        default: gemini-pro
      - name: body
        in: body
        required: true
        description: Same as generateContent but responses are streamed
        schema:
          type: object
          properties:
            contents:
              type: array
              items:
                type: object
          example:
            contents:
              - parts:
                  - text: "Tell me a long story"
    responses:
      200:
        description: Streaming response
      400:
        description: Bad request
      503:
        description: No healthy API keys available
    """
    return proxy(f'v1beta/models/{model_name}:streamGenerateContent')

@proxy_bp.route('/v1beta/models/<model_name>:countTokens', methods=['POST'])
@proxy_bp.route('/v1/models/<model_name>:countTokens', methods=['POST'])
def gemini_count_tokens(model_name):
    """
    Count tokens for Gemini API request
    ---
    tags:
      - Gemini API
    parameters:
      - name: model_name
        in: path
        type: string
        required: true
        description: Model name
        default: gemini-pro
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            contents:
              type: array
          example:
            contents:
              - parts:
                  - text: "How many tokens is this?"
    responses:
      200:
        description: Token count
        schema:
          type: object
          properties:
            totalTokens:
              type: integer
      503:
        description: No healthy API keys available
    """
    return proxy(f'v1beta/models/{model_name}:countTokens')

@proxy_bp.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
def proxy(path):
    """
    AI API Proxy - Universal endpoint for Gemini API requests
    ---
    tags:
      - AI Proxy
    parameters:
      - name: path
        in: path
        type: string
        required: true
        description: The API endpoint path (e.g., 'v1beta/models/gemini-pro:generateContent' or 'v1/chat/completions' for OpenAI format)
      - name: body
        in: body
        required: false
        description: Request body for POST/PUT/PATCH requests
        schema:
          type: object
          example:
            contents:
              - parts:
                  - text: "Explain how AI works"
    responses:
      200:
        description: Successful AI API response
        schema:
          type: object
          example:
            candidates:
              - content:
                  parts:
                    - text: "AI works by..."
            usageMetadata:
              promptTokenCount: 10
              candidatesTokenCount: 50
      400:
        description: Bad request
      502:
        description: Network error from upstream API
      503:
        description: No healthy API keys available
    examples:
      gemini_native:
        summary: "Gemini Native Format"
        value:
          path: "v1beta/models/gemini-pro:generateContent"
          method: "POST"
          body:
            contents:
              - parts:
                  - text: "Hello, how are you?"
      openai_compatible:
        summary: "OpenAI Compatible Format"
        value:
          path: "v1/chat/completions"
          method: "POST"
          body:
            model: "gemini-pro"
            messages:
              - role: "user"
                content: "Hello, how are you?"
    """
    start_time = time.time()
    
    # --- Universal Translator Logic ---
    target_base_url = "https://generativelanguage.googleapis.com/"
    provider_format = 'gemini' # Default to Gemini
    path_to_proxy = path

    # Determine if it's an OpenAI formatted request. This is more robust.
    if 'openai' in path or path.startswith('v1/'):
        provider_format = 'openai'
    
    # Model Name Extraction
    model_name = "unknown"
    try:
        if provider_format == 'gemini':
            if 'models' in path_to_proxy and not ':' in path_to_proxy:
                 model_name = "model-discovery"
            else:
                 model_name = path_to_proxy.split('/')[-1].split(':')[0]
        elif provider_format == 'openai':
            if request.data:
                model_name = request.get_json(silent=True).get('model', 'unknown')
            elif path_to_proxy.endswith('/models'):
                 model_name = "model-discovery"
    except Exception:
        pass # Silently fail, model_name remains "unknown"

    add_log_entry(f"Incoming {provider_format.upper()}-format request for model: {model_name}...")
    
    # Cache request data for potential retries
    request_data = request.get_data()
    request_params = request.args
    
    # Retry logic with automatic failover
    max_retries = 1
    tried_key_ids = []
    
    for attempt in range(max_retries + 1):
        key_info = key_manager.get_next_key(exclude_ids=tried_key_ids if tried_key_ids else None)

        if not key_info:
            add_log_entry(f"No healthy keys available!", "text-red-500")
            return jsonify({"error": f"No healthy API keys available."}), 503

        key_id, api_key = key_info['id'], key_info['key_value']
        tried_key_ids.append(key_id)
        
        if attempt > 0:
            add_log_entry(f"Retry #{attempt} with Key '{key_info['name']}' (...{api_key[-4:]})", "text-yellow-400")
        else:
            add_log_entry(f"Routing to Key '{key_info['name']}' (...{api_key[-4:]})", "text-blue-400")
        
        # --- URL and Header Construction ---
        headers = {k: v for k, v in request.headers if k.lower() not in ['host', 'authorization', 'x-goog-api-key']}
        target_url = target_base_url + path_to_proxy
        
        # FIX: Set the correct authentication header based on the detected format
        if provider_format == 'openai':
            headers['Authorization'] = f"Bearer {api_key}"
        else: # Default to Gemini format
            headers['x-goog-api-key'] = api_key
        
        if 'Content-Type' not in headers: headers['Content-Type'] = 'application/json'

        try:
            resp = requests.request(method=request.method, url=target_url, headers=headers, data=request_data, params=request_params)
            latency_ms = int((time.time() - start_time) * 1000)
            response_content = resp.content
            
            tokens_in, tokens_out = 0, 0
            if resp.ok:
                add_log_entry(f"SUCCESS ({resp.status_code}) from '{key_info['name']}' in {latency_ms}ms.", "text-green-400")
                try:
                    data = json.loads(response_content)
                    # Google's OpenAI-compatible endpoint uses 'usage' like OpenAI
                    if 'usage' in data:
                        usage = data.get('usage', {})
                        tokens_in = usage.get('prompt_tokens', 0)
                        tokens_out = usage.get('completion_tokens', 0)
                    # Native Gemini endpoint uses 'usageMetadata'
                    elif 'usageMetadata' in data:
                        usage = data.get('usageMetadata', {})
                        tokens_in = usage.get('promptTokenCount', 0)
                        tokens_out = usage.get('candidatesTokenCount', 0)
                except (json.JSONDecodeError, KeyError): pass
                
                key_manager.update_key_stats(key_id, True, model_name,
                    error_code=None, tokens_in=tokens_in, tokens_out=tokens_out, latency_ms=latency_ms)
                    
                return Response(response_content, status=resp.status_code, content_type=resp.headers.get('Content-Type'))
            
            # Handle error responses
            else:
                add_log_entry(f"ERROR ({resp.status_code}) from '{key_info['name']}'.", "text-red-500")
                key_manager.update_key_stats(key_id, False, model_name,
                    error_code=resp.status_code, latency_ms=latency_ms)
                
                # Retry on 503 only, and only if we haven't exceeded max retries
                if resp.status_code == 503 and attempt < max_retries:
                    add_log_entry(f"503 detected, attempting failover to another key...", "text-orange-400")
                    continue
                
                # For all other errors or if max retries reached, return the error
                return Response(response_content, status=resp.status_code, content_type=resp.headers.get('Content-Type'))
                
        except requests.exceptions.RequestException as e:
            latency_ms = int((time.time() - start_time) * 1000)
            add_log_entry(f"NETWORK ERROR on key '{key_info['name']}'! {e}", "text-orange-500")
            key_manager.update_key_stats(key_id, False, model_name, error_code=599, latency_ms=latency_ms)
            
            # Retry on network errors if we haven't exceeded max retries
            if attempt < max_retries:
                add_log_entry(f"Network error detected, attempting failover to another key...", "text-orange-400")
                continue
            
            return jsonify({"error": "Middleware network error"}), 502
    
    # If we've exhausted all retries
    add_log_entry(f"All retry attempts exhausted.", "text-red-500")
    return jsonify({"error": "All keys failed after retries"}), 503
