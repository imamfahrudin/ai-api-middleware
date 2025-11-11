# Timeout Configuration Guide

This document explains the enhanced timeout configuration in the AI API Middleware proxy, including behavior, settings, and edge cases.

## Overview

The proxy now supports comprehensive timeout configuration with different timeout types for various scenarios:

- **Connection Timeout**: Time to establish the initial connection
- **Read Timeout**: Time to wait for data after connection is established
- **Streaming Timeout**: Time to wait for each chunk during streaming
- **Request Timeout**: Legacy timeout (still supported for backward compatibility)

## Configuration Settings

All timeout settings are configured via the application settings interface or database:

### New Timeout Settings

| Setting | Default | Description | Recommended Range |
|---------|---------|-------------|------------------|
| `connect_timeout` | 10 seconds | Time to establish TCP connection | 5-30 seconds |
| `read_timeout` | 60 seconds | Time to wait for response headers/initial data | 30-120 seconds |
| `streaming_timeout` | 120 seconds | Time to wait for each streaming chunk | 60-300 seconds |
| `request_timeout` | 30 seconds | Legacy setting (still supported) | 10-60 seconds |

### Legacy Setting

The `request_timeout` setting is still supported for backward compatibility. When both legacy and new settings are configured:

1. The proxy prioritizes `connect_timeout` + `read_timeout` for connection establishment
2. Uses `streaming_timeout` for streaming operations
3. Falls back to `request_timeout` if new settings are not available

## Timeout Behavior

### Connection Phase

- Uses `connect_timeout` from settings or defaults to 10 seconds
- Combined with `read_timeout` as a tuple: `(connect_timeout, read_timeout)`
- Applied to both connection pooling and direct requests

### Streaming Phase

- Each chunk from `iter_content()` uses `streaming_timeout`
- Separate from connection timeouts to handle long-running streams
- Default: 120 seconds per chunk

### Error Handling

1. **Connection Timeouts**: Triggers key failover and retry logic
2. **Read Timeouts**: Triggers retry with exponential backoff
3. **Streaming Timeouts**: Implements chunk-level retry with graceful degradation

## Streaming with Retry Logic

The enhanced streaming includes:

### Automatic Retry
- **Max Retries**: 2 attempts per failed chunk
- **Backoff Strategy**: Exponential (1s, 2s, 4s...)
- **Graceful Degradation**: Attempts to provide partial response on complete failure

### Resource Management
- Automatic connection cleanup on all paths
- Proper response object closing in `finally` blocks
- Memory-efficient buffer management

### Error Recovery
```python
# Example of streaming with retry behavior
try:
    for chunk in stream_with_retry(resp, buffer_size, streaming_timeout, max_stream_retries=2):
        yield chunk
except Exception as e:
    # Attempt graceful degradation
    try:
        remaining_content = resp.content
        if remaining_content:
            yield remaining_content
    except Exception:
        # Complete failure handled by caller
        pass
```

## Buffer Size Optimization

Buffer sizes are automatically optimized based on:

- **Request Size**: Smaller buffers for small requests (< 1KB)
- **Content Type**: Optimized buffers for text vs binary content
- **Upper/Lower Bounds**: Constrained between 1KB and 64KB

### Optimization Rules

1. **Small Requests (< 1KB) or Text Content**: Max 4KB buffer
2. **Large Requests (> 100KB) or Binary Content**: Min 16KB buffer
3. **Default**: 8KB buffer size
4. **Bounds**: 1KB minimum, 64KB maximum

## Connection Pooling

The HTTP session is dynamically reconfigured based on timeout settings:

- **Retry Strategy**: 7 total attempts (increased from 3)
- **Backoff Factor**: 0.1 seconds between retries
- **Status Codes**: Retries on 429, 500, 502, 503, 504
- **Methods**: Supports all common HTTP methods

## Edge Cases and Behavior

### Network Interruptions

- **Partial Streams**: Graceful degradation attempts to provide partial responses
- **Connection Drops**: Automatic failover to alternative API keys
- **Timeout Expiration**: Proper cleanup and resource release

### Resource Constraints

- **Memory Usage**: Bounded buffer sizes prevent memory exhaustion
- **Connection Limits**: Connection pooling with max 100 connections
- **Timeout Bounds**: All timeouts constrained to reasonable ranges

### Error Scenarios

1. **Immediate Timeout**: Treated as network error, triggers key failover
2. **Partial Timeout**: Attempts graceful degradation
3. **Repeated Timeouts**: Marks key as resting (rate limit) or disabled

## Monitoring and Logging

Comprehensive logging provides visibility into:

- **Timeout Events**: All timeout occurrences with context
- **Retry Attempts**: Number and timing of retries
- **Buffer Sizes**: Dynamic buffer adjustments
- **Resource Cleanup**: Connection close success/failure

### Log Messages

```
[INFO] Using optimized buffer size: 4096 bytes (request: 512 bytes)
[WARN] Streaming chunk failed (attempt 1/2): Read timed out. Retrying in 1.0s...
[INFO] Providing partial response: 2048 bytes
[ERROR] Streaming failed after 2 retry attempts: Connection broken
```

## Testing

The timeout behavior is validated with automated tests:

- **Configuration Parsing**: Validates timeout setting conversion
- **Streaming Retry Logic**: Tests chunk-level retry behavior
- **Buffer Optimization**: Verifies dynamic buffer adjustment
- **Resource Cleanup**: Ensures proper connection management

Run tests with:
```bash
python test_proxy_enhancements.py
```

## Best Practices

### Configuration Recommendations

1. **Conservative Timeouts**: Start with defaults, adjust based on API performance
2. **Monitor Logs**: Watch for timeout patterns and adjust accordingly
3. **API Key Health**: Monitor key status and resting patterns
4. **Network Conditions**: Consider latency for different regions

### Performance Tuning

1. **Buffer Size**: Adjust based on typical request sizes
2. **Streaming Timeout**: Increase for long-generation AI responses
3. **Connection Pooling**: Enable for high-traffic scenarios
4. **Retry Logic**: Adjust retry count based on error tolerance

### Monitoring

1. **Timeout Frequency**: Track timeout occurrences per key
2. **Partial Response Rate**: Monitor graceful degradation usage
3. **Connection Pool Health**: Watch pool utilization
4. **Response Times**: Track latency improvements

## Troubleshooting

### Common Issues

1. **Frequent Timeouts**: Increase timeout values or check network connectivity
2. **Partial Responses**: May indicate API rate limiting or network instability
3. **Connection Leaks**: Check logs for "Failed to close response" messages
4. **Memory Usage**: Monitor buffer size adjustments for very large requests

### Debug Information

Enable debug logging to see:
- Timeout value calculations
- Buffer size decisions
- Retry attempt details
- Connection pool status

## Migration Guide

### From Legacy Configuration

If upgrading from a version with only `request_timeout`:

1. **Existing Behavior**: No immediate change - `request_timeout` still works
2. **Recommended Migration**: Add new timeout settings for better control
3. **Gradual Migration**: Can implement new settings incrementally

### Settings Migration

```python
# Old configuration
request_timeout = 30

# New equivalent configuration
connect_timeout = 10    # 1/3 of request_timeout
read_timeout = 60       # 2x request_timeout for streaming
streaming_timeout = 120 # 4x request_timeout for long streams
```

## Future Enhancements

Planned improvements include:

1. **Adaptive Timeouts**: Machine learning-based timeout optimization
2. **Per-Provider Settings**: Different timeouts for different AI providers
3. **Circuit Breaker Pattern**: Automatic key isolation on repeated failures
4. **Advanced Metrics**: Detailed timeout analytics and reporting