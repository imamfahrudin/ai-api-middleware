import time
import json
import requests
import uuid
import asyncio
from typing import Optional, Union, List, Dict, Any
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from flask import request, jsonify, Response, Blueprint, g
from functools import lru_cache
import io

from app.database import KeyManager
from app.logging_utils import add_log_entry
from app.mcp_integration import get_mcp_integration, process_request_with_mcp_integration

proxy_bp = Blueprint('proxy', __name__)
key_manager = KeyManager()

# Performance optimization: Connection pooling for HTTP requests
session = requests.Session()
retry_strategy = Retry(
    total=3,
    backoff_factor=0.1,
    status_forcelist=[429, 500, 502, 503, 504],
)
adapter = HTTPAdapter(
    pool_connections=20,
    pool_maxsize=100,
    max_retries=retry_strategy
)
session.mount("http://", adapter)
session.mount("https://", adapter)

# Performance optimization: Cache for model discovery responses
_model_cache = {}
_cache_timeout = 300  # 5 minutes TTL

def get_cached_models_list(api_key, path):
    """Cache model list responses for 5 minutes to reduce API calls"""
    cache_key = f"{api_key}:{path}"
    current_time = time.time()

    # Check if we have a cached response that's still valid
    if cache_key in _model_cache:
        cached_data, timestamp = _model_cache[cache_key]
        if current_time - timestamp < _cache_timeout:
            return cached_data

    # If not cached or expired, fetch new data
    try:
        headers = {'x-goog-api-key': api_key, 'Content-Type': 'application/json'}
        url = f"https://generativelanguage.googleapis.com/{path}"
        resp = session.get(url, headers=headers, timeout=10)
        if resp.ok:
            data = resp.json()
            _model_cache[cache_key] = (data, current_time)
            return data
        return None
    except Exception:
        return None

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
    # Performance optimization: Use cached response for model lists if enabled
    model_cache_enabled = key_manager.get_setting('model_cache_enabled', 'true').lower() == 'true'

    if model_cache_enabled:
        key_info = key_manager.get_next_key()
        if not key_info:
            return jsonify({"error": "No healthy API keys available."}), 503

        api_key = key_info['key_value']
        path = 'v1beta/models'

        # Try to get from cache first
        cached_response = get_cached_models_list(api_key, path)
        if cached_response:
            add_log_entry(f"Cache HIT for models list", "text-green-400")
            return jsonify(cached_response)

        add_log_entry(f"Cache MISS for models list", "text-yellow-400")

    return proxy(path)

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
    
    # Performance optimization: Model Name Extraction with reduced operations
    model_name = "unknown"

    if provider_format == 'gemini':
        if 'models' in path_to_proxy and ':' not in path_to_proxy:
            model_name = "model-discovery"
        else:
            # Performance optimization: Use rfind for better performance on long paths
            colon_pos = path_to_proxy.rfind(':')
            slash_pos = path_to_proxy.rfind('/')
            if colon_pos > slash_pos:
                model_name = path_to_proxy[slash_pos + 1:colon_pos]
            else:
                model_name = path_to_proxy[slash_pos + 1:] if slash_pos >= 0 else path_to_proxy
    elif provider_format == 'openai':
        if request_data:
            # Performance optimization: Avoid JSON parsing if we can find model quickly
            try:
                # Quick string search for "model" key before full JSON parse
                if b'"model"' in request_data:
                    json_data = request.get_json(silent=True)
                    if json_data:
                        model_name = json_data.get('model', 'unknown')
            except Exception:
                pass  # Silently fail, model_name remains "unknown"
        elif path_to_proxy.endswith('/models'):
            model_name = "model-discovery"

    # Cache request data for potential reuse
    request_data = request.get_data()

    add_log_entry(f"Incoming {provider_format.upper()}-format request for model: {model_name}...")

    # --- MCP Integration Check ---
    # Extract user request text for MCP analysis
    user_request_text = _extract_user_request_text(request_data, provider_format)

    # Extract session ID from headers or create new one
    session_id = request.headers.get('X-MCP-Session-ID')
    request_id = getattr(g, 'request_id', None)

    # Check if MCP tools should be used (only for content generation requests)
    mcp_result = None
    should_use_mcp = (user_request_text and
                     model_name not in ["model-discovery", "unknown"] and
                     key_manager.get_setting('mcp_enabled', 'false').lower() == 'true' and
                     key_manager.get_setting('mcp_auto_detect_tools', 'true').lower() == 'true')

    if should_use_mcp and user_request_text:
        try:
            # Prepare request data with additional context
            mcp_request_data = {
                'provider_format': provider_format,
                'model': model_name,
                'request_id': request_id,
                'ip_address': request.environ.get('REMOTE_ADDR'),
                'user_agent': request.headers.get('User-Agent', ''),
                'headers': dict(request.headers)
            }

            # Run MCP processing in async context
            loop = None
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            if loop.is_running():
                # If loop is already running, we need to run in a thread
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, process_request_with_mcp_integration(
                        user_request_text, mcp_request_data, session_id
                    ))
                    mcp_result = future.result(timeout=30)  # 30 second timeout
            else:
                mcp_result = loop.run_until_complete(process_request_with_mcp_integration(
                    user_request_text, mcp_request_data, session_id
                ))

            # If MCP provided a complete response, return it directly
            if mcp_result and mcp_result.get('requires_mcp') and mcp_result.get('response'):
                add_log_entry(f"MCP: Provided complete response with {len(mcp_result.get('tool_results', []))} tools", "text-green-400")

                # Format response according to the original request format
                formatted_response = _format_mcp_response_for_client(
                    mcp_result['response'],
                    provider_format,
                    model_name,
                    mcp_result.get('tool_results', [])
                )

                # Return the MCP-enhanced response
                response_data = formatted_response
                response = None

                if isinstance(formatted_response, dict):
                    response = jsonify(formatted_response)
                else:
                    response = Response(formatted_response, content_type=_get_content_type(provider_format))

                # Add session ID to response headers if available
                if mcp_result and mcp_result.get('session_id'):
                    response.headers['X-MCP-Session-ID'] = mcp_result['session_id']

                return response

            # If MCP detected tools but didn't provide complete response,
            # we'll continue with AI API and can potentially enhance the response later
            elif mcp_result and mcp_result.get('requires_mcp'):
                add_log_entry(f"MCP: Tools detected but proceeding with AI for enhancement", "text-yellow-400")

        except Exception as e:
            add_log_entry(f"MCP: Integration error - {str(e)}", "text-red-500")
            logger.error(f"MCP integration error: {str(e)}")

    # Cache request params for potential retries
    request_params = request.args
    
    # Retry logic with automatic failover - get from settings
    max_retries = key_manager.get_setting('max_retries', '7')
    try:
        max_retries = int(max_retries)
    except (ValueError, TypeError):
        max_retries = 7
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
        # Performance optimization: Pre-compute lowercase header exclusions for faster lookup
        excluded_headers = {'host', 'authorization', 'x-goog-api-key'}
        headers = {}
        for k, v in request.headers:
            lk = k.lower()
            if lk not in excluded_headers:
                headers[k] = v

        target_url = target_base_url + path_to_proxy

        # FIX: Set the correct authentication header based on the detected format
        if provider_format == 'openai':
            headers['Authorization'] = f"Bearer {api_key}"
        else: # Default to Gemini format
            headers['x-goog-api-key'] = api_key

        # Performance optimization: Avoid dict lookup if we already know the header exists
        if 'Content-Type' not in headers:
            headers['Content-Type'] = 'application/json'

        try:
            # Get settings for this request
            streaming_enabled = key_manager.get_setting('streaming_enabled', 'true').lower() == 'true'
            connection_pooling_enabled = key_manager.get_setting('connection_pooling_enabled', 'true').lower() == 'true'
            buffer_size_setting = key_manager.get_setting('buffer_size', '8192')
            enable_request_id_injection = key_manager.get_setting('enable_request_id_injection', 'true').lower() == 'true'

            # Convert buffer_size to int with fallback
            try:
                buffer_size = int(buffer_size_setting)
            except (ValueError, TypeError):
                buffer_size = 8192

            # Add request ID if enabled
            if enable_request_id_injection:
                request_id = str(uuid.uuid4())
                headers['X-Request-ID'] = request_id
                add_log_entry(f"Request ID injected: {request_id}", "text-gray-400")

            # Choose request method based on settings
            if connection_pooling_enabled:
                # Use session with connection pooling
                resp = session.request(method=request.method, url=target_url, headers=headers, data=request_data, params=request_params, stream=streaming_enabled)
            else:
                # Use direct requests without connection pooling
                resp = requests.request(method=request.method, url=target_url, headers=headers, data=request_data, params=request_params, stream=streaming_enabled)

            latency_ms = int((time.time() - start_time) * 1000)

            tokens_in, tokens_out = 0, 0
            if resp.ok:
                add_log_entry(f"SUCCESS ({resp.status_code}) from '{key_info['name']}' in {latency_ms}ms.", "text-green-400")

                if streaming_enabled:
                    # Performance optimization: Stream response for better memory usage
                    def generate():
                        nonlocal tokens_in, tokens_out
                        json_start_buffer = b""
                        json_buffer_size = 0

                        for chunk in resp.iter_content(chunk_size=buffer_size):
                            if chunk:
                                # Yield chunk immediately for streaming
                                yield chunk

                                # Performance optimization: Only buffer first 2KB for token extraction
                                if json_buffer_size < 2048:
                                    remaining = 2048 - json_buffer_size
                                    json_start_buffer += chunk[:remaining]
                                    json_buffer_size += len(chunk)

                        # Parse token usage from buffered content
                        try:
                            if json_start_buffer:
                                data = json.loads(json_start_buffer.decode('utf-8', errors='ignore'))
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
                        except (json.JSONDecodeError, KeyError, UnicodeDecodeError):
                            pass

                    # Create and return the streaming response
                    response = Response(generate(), status=resp.status_code, content_type=resp.headers.get('Content-Type'))
                else:
                    # Traditional non-streaming response
                    response_content = resp.content
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
                    except (json.JSONDecodeError, KeyError):
                        pass

                    response = Response(response_content, status=resp.status_code, content_type=resp.headers.get('Content-Type'))

                # Update stats after creating response
                key_manager.update_key_stats(key_id, True, model_name,
                    error_code=None, tokens_in=tokens_in, tokens_out=tokens_out, latency_ms=latency_ms)

                return response
            
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
                if streaming_enabled:
                    # Performance optimization: Stream error responses too
                    def error_generate():
                        for chunk in resp.iter_content(chunk_size=buffer_size):
                            if chunk:
                                yield chunk

                    return Response(error_generate(), status=resp.status_code, content_type=resp.headers.get('Content-Type'))
                else:
                    # Traditional non-streaming error response
                    return Response(resp.content, status=resp.status_code, content_type=resp.headers.get('Content-Type'))
                
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


# --- MCP Helper Functions ---

def _extract_user_request_text(request_data: bytes, provider_format: str) -> Optional[str]:
    """
    Extract user request text from request data for MCP analysis

    Args:
        request_data: Raw request data
        provider_format: 'gemini' or 'openai'

    Returns:
        Extracted user text or None
    """
    try:
        if not request_data:
            return None

        json_data = json.loads(request_data.decode('utf-8'))

        if provider_format == 'gemini':
            # Extract from Gemini format
            contents = json_data.get('contents', [])
            if contents and isinstance(contents, list):
                for content in contents:
                    parts = content.get('parts', [])
                    if parts and isinstance(parts, list):
                        for part in parts:
                            if 'text' in part:
                                return part['text']

        elif provider_format == 'openai':
            # Extract from OpenAI format
            messages = json_data.get('messages', [])
            if messages and isinstance(messages, list):
                # Get the last user message
                for message in reversed(messages):
                    if message.get('role') == 'user':
                        content = message.get('content')
                        if isinstance(content, str):
                            return content
                        elif isinstance(content, list):
                            # Handle structured content
                            text_parts = []
                            for part in content:
                                if part.get('type') == 'text':
                                    text_parts.append(part.get('text', ''))
                            return ' '.join(text_parts) if text_parts else None

        return None

    except (json.JSONDecodeError, UnicodeDecodeError, KeyError, TypeError) as e:
        logger.error(f"Error extracting user request text: {str(e)}")
        return None

def _format_mcp_response_for_client(mcp_response: str, provider_format: str,
                                   model_name: str, tool_results: List[Dict[str, Any]]) -> Union[dict, str]:
    """
    Format MCP response for the client according to the provider format

    Args:
        mcp_response: The MCP response text
        provider_format: 'gemini' or 'openai'
        model_name: Model name for the response
        tool_results: List of tool results used

    Returns:
        Formatted response (dict for JSON, str for text)
    """
    try:
        # Add tool attribution to response
        attribution = ""
        if tool_results:
            successful_tools = [t for t in tool_results if t.get('success')]
            if successful_tools:
                tool_names = [t.get('tool_name', 'unknown') for t in successful_tools]
                attribution = f"\n\n*(Response enhanced using tools: {', '.join(tool_names)})*"

        full_response = mcp_response + attribution

        if provider_format == 'gemini':
            # Gemini format
            return {
                "candidates": [{
                    "content": {
                        "parts": [{
                            "text": full_response
                        }],
                        "role": "model"
                    },
                    "finishReason": "STOP"
                }],
                "usageMetadata": {
                    "promptTokenCount": 0,  # Would need actual token counting
                    "candidatesTokenCount": 0,
                    "totalTokenCount": 0
                }
            }

        elif provider_format == 'openai':
            # OpenAI format
            return {
                "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model_name,
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": full_response
                    },
                    "finish_reason": "stop"
                }],
                "usage": {
                    "prompt_tokens": 0,  # Would need actual token counting
                    "completion_tokens": 0,
                    "total_tokens": 0
                }
            }

        else:
            # Fallback to plain text
            return full_response

    except Exception as e:
        logger.error(f"Error formatting MCP response: {str(e)}")
        # Fallback to plain text
        return mcp_response

def _get_content_type(provider_format: str) -> str:
    """Get appropriate content type for provider format"""
    if provider_format in ['gemini', 'openai']:
        return 'application/json'
    else:
        return 'text/plain'
