import time
import json
import requests
import uuid
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from flask import request, jsonify, Response, Blueprint
from functools import lru_cache
import io

from app.database import KeyManager
from app.logging_utils import add_log_entry, log_request, log_response, log_performance

proxy_bp = Blueprint('proxy', __name__)
key_manager = KeyManager()

# Performance optimization: Connection pooling for HTTP requests
session = requests.Session()

def configure_session_timeout(connect_timeout=10, read_timeout=60):
    """Configure session with dynamic timeout settings"""
    # Get retry settings from configuration
    retry_total = key_manager.get_setting('retry_total', '7')
    retry_backoff_factor = key_manager.get_setting('retry_backoff_factor', '0.1')
    pool_connections = key_manager.get_setting('pool_connections', '20')
    pool_maxsize = key_manager.get_setting('pool_maxsize', '100')

    # Convert to appropriate types with fallbacks
    try:
        retry_total = int(retry_total)
    except (ValueError, TypeError):
        retry_total = 7

    try:
        retry_backoff_factor = float(retry_backoff_factor)
    except (ValueError, TypeError):
        retry_backoff_factor = 0.1

    try:
        pool_connections = int(pool_connections)
    except (ValueError, TypeError):
        pool_connections = 20

    try:
        pool_maxsize = int(pool_maxsize)
    except (ValueError, TypeError):
        pool_maxsize = 100

    retry_strategy = Retry(
        total=retry_total,
        backoff_factor=retry_backoff_factor,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS", "TRACE"]
    )
    adapter = HTTPAdapter(
        pool_connections=pool_connections,
        pool_maxsize=pool_maxsize,
        max_retries=retry_strategy
    )
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    # Configure default timeouts for the session
    session.timeout = (connect_timeout, read_timeout)

# Initialize with default timeouts
configure_session_timeout()

def stream_with_retry(resp, buffer_size, streaming_timeout, max_stream_retries=None):
    """
    Stream content with retry logic for failed chunks.
    Returns a generator that yields chunks with retry capability.
    """
    # Get stream retry settings from configuration
    if max_stream_retries is None:
        max_stream_retries_setting = key_manager.get_setting('max_stream_retries', '2')
        try:
            max_stream_retries = int(max_stream_retries_setting)
        except (ValueError, TypeError):
            max_stream_retries = 2

    chunk_retry_delay_setting = key_manager.get_setting('chunk_retry_delay', '1.0')
    try:
        chunk_retry_delay = float(chunk_retry_delay_setting)
    except (ValueError, TypeError):
        chunk_retry_delay = 1.0

    retry_count = 0
    recursion_depth = 0  # DEBUG: Track recursion depth to detect potential stack overflow

    def stream_generator():
        nonlocal retry_count, chunk_retry_delay, recursion_depth
        response_closed = False
        
        # DEBUG: Track recursion depth
        recursion_depth += 1
        if recursion_depth > 5:  # Arbitrary threshold to detect problematic recursion
            add_log_entry(f"BUG WARNING: Excessive recursion depth detected: {recursion_depth}", "text-red-600")

        try:
            for chunk in resp.iter_content(chunk_size=buffer_size):
                if chunk:
                    yield chunk
                    # Reset retry count on successful chunk
                    retry_count = 0
                    chunk_retry_delay = 1.0

        except Exception as e:
            retry_count += 1
            if retry_count <= max_stream_retries:
                add_log_entry(f"Streaming chunk failed (attempt {retry_count}/{max_stream_retries}, recursion depth: {recursion_depth}): {e}. Retrying in {chunk_retry_delay}s...", "text-orange-400")
                time.sleep(chunk_retry_delay)
                chunk_retry_delay *= 2  # Exponential backoff
                # Continue trying to read remaining chunks
                try:
                    for remaining_chunk in stream_generator():
                        yield remaining_chunk
                except Exception as recurse_error:
                    # Don't recurse infinitely on repeated errors
                    add_log_entry(f"BUG CONFIRMED: Recursive streaming failed: {recurse_error}", "text-red-600")
                    pass
            else:
                add_log_entry(f"Streaming failed after {max_stream_retries} retry attempts: {e}", "text-red-500")
                # Don't raise - just stop streaming to allow graceful degradation

        finally:
            # Always close the response when generator is exhausted or exits
            if not response_closed and hasattr(resp, 'close'):
                try:
                    resp.close()
                    response_closed = True
                except Exception as close_error:
                    add_log_entry(f"Failed to close response in stream_with_retry: {close_error}", "text-orange-500")
            
            # DEBUG: Decrement recursion depth when exiting
            recursion_depth -= 1

    return stream_generator()

# Performance optimization: Cache for model discovery responses
_model_cache = {}

def get_cache_timeout():
    """Get cache timeout from settings"""
    cache_timeout_setting = key_manager.get_setting('cache_timeout', '300')
    try:
        return int(cache_timeout_setting)
    except (ValueError, TypeError):
        return 300

def get_cached_models_list(api_key, path):
    """Cache model list responses for configurable time to reduce API calls"""
    cache_key = f"{api_key}:{path}"
    current_time = time.time()
    cache_timeout = get_cache_timeout()

    # Check if we have a cached response that's still valid
    if cache_key in _model_cache:
        cached_data, timestamp = _model_cache[cache_key]
        if current_time - timestamp < cache_timeout:
            return cached_data

    # If not cached or expired, fetch new data
    try:
        headers = {'x-goog-api-key': api_key, 'Content-Type': 'application/json'}
        url = f"https://generativelanguage.googleapis.com/{path}"

        # Get model cache timeout from settings
        model_cache_timeout_setting = key_manager.get_setting('model_cache_timeout', '10')
        try:
            model_cache_timeout = int(model_cache_timeout_setting)
        except (ValueError, TypeError):
            model_cache_timeout = 10

        resp = session.get(url, headers=headers, timeout=model_cache_timeout)
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

    # --- Handle Static File Requests ---
    if path == 'favicon.ico':
        # Return a simple 404 for favicon requests to avoid proxying them
        return '', 404

    # --- Logging Configuration Check ---
    enable_request_logging = key_manager.get_setting('enable_request_logging', 'true').lower() == 'true'
    log_request_body = key_manager.get_setting('log_request_body', 'false').lower() == 'true'
    log_response_body = key_manager.get_setting('log_response_body', 'false').lower() == 'true'
    enable_performance_logging = key_manager.get_setting('enable_performance_logging', 'true').lower() == 'true'
    enable_metrics_collection = key_manager.get_setting('enable_metrics_collection', 'true').lower() == 'true'

    # Log incoming request if enabled
    if enable_request_logging:
        request_body_data = None
        if log_request_body:
            try:
                request_body_data = request.get_json() if request.is_json else request.get_data(as_text=True)
            except Exception:
                request_body_data = "[Failed to parse request body]"
        
        log_request(
            method=request.method,
            path=path,
            headers=dict(request.headers),
            body=request_body_data,
            request_id=request.headers.get('X-Request-ID')
        )

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
        # DEBUG: Check if request_data is defined before using it
        try:
            if request_data:
                add_log_entry(f"DEBUG: request_data found with length: {len(request_data)}", "text-blue-300")
                # Performance optimization: Avoid JSON parsing if we can find model quickly
                try:
                    # Quick string search for "model" key before full JSON parse
                    if b'"model"' in request_data:
                        json_data = request.get_json(silent=True)
                        if json_data:
                            model_name = json_data.get('model', 'unknown')
                except Exception:
                    pass  # Silently fail, model_name remains "unknown"
            else:
                add_log_entry("DEBUG: request_data is None or empty", "text-blue-300")
        except NameError as e:
            add_log_entry(f"BUG CONFIRMED: request_data used before definition - {e}", "text-red-600")
            
        if path_to_proxy.endswith('/models'):
            model_name = "model-discovery"

    add_log_entry(f"Incoming {provider_format.upper()}-format request for model: {model_name}...")
    
    # Cache request data for potential retries
    request_data = request.get_data()
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
            request_timeout_setting = key_manager.get_setting('request_timeout', '30')
            connect_timeout_setting = key_manager.get_setting('connect_timeout', '10')
            read_timeout_setting = key_manager.get_setting('read_timeout', '60')
            streaming_timeout_setting = key_manager.get_setting('streaming_timeout', '120')

            # Convert settings to appropriate types with fallbacks
            try:
                buffer_size = int(buffer_size_setting)
            except (ValueError, TypeError):
                buffer_size = 8192

            # Optimize buffer size based on content type and request characteristics
            content_type = headers.get('Content-Type', '')
            request_size = len(request_data) if request_data else 0

            # Get buffer optimization thresholds from settings
            small_request_threshold = key_manager.get_setting('small_request_threshold', '1024')
            large_request_threshold = key_manager.get_setting('large_request_threshold', '100000')
            small_buffer_size = key_manager.get_setting('small_buffer_size', '4096')
            large_buffer_size = key_manager.get_setting('large_buffer_size', '16384')
            min_buffer_size = key_manager.get_setting('min_buffer_size', '1024')
            max_buffer_size = key_manager.get_setting('max_buffer_size', '65536')

            # Convert to appropriate types with fallbacks
            try:
                small_request_threshold = int(small_request_threshold)
            except (ValueError, TypeError):
                small_request_threshold = 1024

            try:
                large_request_threshold = int(large_request_threshold)
            except (ValueError, TypeError):
                large_request_threshold = 100000

            try:
                small_buffer_size = int(small_buffer_size)
            except (ValueError, TypeError):
                small_buffer_size = 4096

            try:
                large_buffer_size = int(large_buffer_size)
            except (ValueError, TypeError):
                large_buffer_size = 16384

            try:
                min_buffer_size = int(min_buffer_size)
            except (ValueError, TypeError):
                min_buffer_size = 1024

            try:
                max_buffer_size = int(max_buffer_size)
            except (ValueError, TypeError):
                max_buffer_size = 65536

            # Smaller buffers for small requests or text responses
            if request_size < small_request_threshold or 'text/' in content_type:
                buffer_size = min(buffer_size, small_buffer_size)
            # Larger buffers for binary/large content
            elif request_size > large_request_threshold or 'application/octet-stream' in content_type:
                buffer_size = max(buffer_size, large_buffer_size)

            # Ensure buffer size is within reasonable bounds
            buffer_size = max(min_buffer_size, min(buffer_size, max_buffer_size))

            add_log_entry(f"Using optimized buffer size: {buffer_size} bytes (request: {request_size} bytes)", "text-gray-400")

            try:
                request_timeout = int(request_timeout_setting)
            except (ValueError, TypeError):
                request_timeout = 30

            try:
                connect_timeout = int(connect_timeout_setting)
            except (ValueError, TypeError):
                connect_timeout = 10

            try:
                read_timeout = int(read_timeout_setting)
            except (ValueError, TypeError):
                read_timeout = 60

            try:
                streaming_timeout = int(streaming_timeout_setting)
            except (ValueError, TypeError):
                streaming_timeout = 120

            # Create timeout tuple for requests (connect_timeout, read_timeout)
            request_timeout_tuple = (connect_timeout, min(read_timeout, streaming_timeout))

            # Add request ID if enabled
            request_id = None
            if enable_request_id_injection:
                request_id = str(uuid.uuid4())
                headers['X-Request-ID'] = request_id
                add_log_entry(f"Request ID injected: {request_id}", "text-gray-400")

            # Choose request method based on settings
            if connection_pooling_enabled:
                # Reconfigure session with current timeout settings
                configure_session_timeout(connect_timeout, min(read_timeout, streaming_timeout))

                # Use session with connection pooling
                resp = session.request(method=request.method, url=target_url, headers=headers, data=request_data, params=request_params, stream=streaming_enabled, timeout=request_timeout_tuple)
            else:
                # Use direct requests without connection pooling
                resp = requests.request(method=request.method, url=target_url, headers=headers, data=request_data, params=request_params, stream=streaming_enabled, timeout=request_timeout_tuple)

            latency_ms = int((time.time() - start_time) * 1000)
            
            # Log performance metrics if enabled
            if enable_performance_logging:
                log_performance(
                    operation=f"{request.method} {path}",
                    duration_ms=latency_ms,
                    details=f"Key: {key_info['name']}, Status: {resp.status_code}"
                )

            tokens_in, tokens_out = 0, 0
            if resp.ok:
                add_log_entry(f"SUCCESS ({resp.status_code}) from '{key_info['name']}' in {latency_ms}ms.", "text-green-400")

                if streaming_enabled:
                    # Performance optimization: Stream response for better memory usage
                    def generate():
                        nonlocal tokens_in, tokens_out
                        json_start_buffer = b""
                        json_buffer_size = 0
                        streaming_error = False
                        response_closed = False

                        try:
                            # Use stream_with_retry for robust streaming with retries
                            for chunk in stream_with_retry(resp, buffer_size, streaming_timeout):
                                if chunk:
                                    # Yield chunk immediately for streaming
                                    yield chunk

                                    # Performance optimization: Only buffer configurable size for token extraction
                                    json_buffer_limit_setting = key_manager.get_setting('json_buffer_limit', '2048')
                                    try:
                                        json_buffer_limit = int(json_buffer_limit_setting)
                                    except (ValueError, TypeError):
                                        json_buffer_limit = 2048

                                    if json_buffer_size < json_buffer_limit:
                                        remaining = json_buffer_limit - json_buffer_size
                                        json_start_buffer += chunk[:remaining]
                                        json_buffer_size += len(chunk)
                        except Exception as e:
                            # Log streaming errors but still try to provide partial response
                            add_log_entry(f"Streaming error after retries: {e}. Attempting graceful degradation.", "text-orange-500")
                            streaming_error = True

                            # Try to extract any remaining content from the response
                            try:
                                remaining_content = resp.content
                                if remaining_content:
                                    add_log_entry(f"Providing partial response: {len(remaining_content)} bytes", "text-yellow-500")
                                    yield remaining_content
                            except Exception as fallback_error:
                                add_log_entry(f"Failed to provide partial response: {fallback_error}", "text-red-500")

                        # Parse token usage from buffered content only if no streaming errors
                        if not streaming_error:
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

                    # Create streaming response with proper headers
                    response = Response(generate(), status=resp.status_code)
                    
                    # Copy important headers from upstream response
                    response_headers = {}
                    for header_name in ['Content-Type', 'Transfer-Encoding', 'Cache-Control']:
                        if header_name in resp.headers:
                            response.headers[header_name] = resp.headers[header_name]
                            response_headers[header_name] = resp.headers[header_name]
                    
                    # Log response if enabled
                    if enable_request_logging:
                        log_response(
                            status_code=resp.status_code,
                            headers=response_headers,
                            body="[Streaming response]" if log_response_body else None,
                            request_id=request_id,
                            latency_ms=latency_ms
                        )
                    
                    # Don't close resp here - let the generator handle it
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
                    
                    # Log response if enabled
                    if enable_request_logging:
                        response_body_data = None
                        if log_response_body:
                            try:
                                response_body_data = json.loads(response_content) if response_content else None
                            except (json.JSONDecodeError, UnicodeDecodeError):
                                response_body_data = f"[Binary data: {len(response_content) if response_content else 0} bytes]"
                        
                        log_response(
                            status_code=resp.status_code,
                            headers=dict(resp.headers),
                            body=response_body_data,
                            request_id=request_id,
                            latency_ms=latency_ms
                        )

                    # Ensure response cleanup for non-streaming responses only
                    try:
                        if hasattr(resp, 'close'):
                            resp.close()
                    except Exception as cleanup_error:
                        add_log_entry(f"Non-streaming response cleanup failed: {cleanup_error}", "text-orange-500")

                # Update stats after creating response (only if metrics collection is enabled)
                if enable_metrics_collection:
                    key_manager.update_key_stats(key_id, True, model_name,
                        error_code=None, tokens_in=tokens_in, tokens_out=tokens_out, latency_ms=latency_ms)

                return response
            
            # Handle error responses
            else:
                add_log_entry(f"ERROR ({resp.status_code}) from '{key_info['name']}'.", "text-red-500")
                
                # Update stats for error response (only if metrics collection is enabled)
                if enable_metrics_collection:
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
                        response_closed = False
                        try:
                            # Use stream_with_retry for robust error streaming with retries
                            for chunk in stream_with_retry(resp, buffer_size, streaming_timeout):
                                if chunk:
                                    yield chunk
                        except Exception as e:
                            # Log error response streaming issues
                            add_log_entry(f"Error response streaming failed after retries: {e}", "text-orange-500")

                    return Response(error_generate(), status=resp.status_code, content_type=resp.headers.get('Content-Type'))
                else:
                    # Traditional non-streaming error response
                    return Response(resp.content, status=resp.status_code, content_type=resp.headers.get('Content-Type'))
                
        except requests.exceptions.RequestException as e:
            latency_ms = int((time.time() - start_time) * 1000)
            
            # Log performance metrics for failed requests if enabled
            if enable_performance_logging:
                log_performance(
                    operation=f"{request.method} {path} (FAILED)",
                    duration_ms=latency_ms,
                    details=f"Key: {key_info['name']}, Error: {str(e)}"
                )
            
            add_log_entry(f"NETWORK ERROR on key '{key_info['name']}'! {e}", "text-orange-500")
            
            # Update stats for network error (only if metrics collection is enabled)
            if enable_metrics_collection:
                key_manager.update_key_stats(key_id, False, model_name, error_code=599, latency_ms=latency_ms)
            
            # Retry on network errors if we haven't exceeded max retries
            if attempt < max_retries:
                add_log_entry(f"Network error detected, attempting failover to another key...", "text-orange-400")
                continue
            
            return jsonify({"error": "Middleware network error"}), 502
    
    # If we've exhausted all retries
    add_log_entry(f"All retry attempts exhausted.", "text-red-500")
    return jsonify({"error": "All keys failed after retries"}), 503
