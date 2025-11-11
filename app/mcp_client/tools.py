"""
MCP Tool Discovery and Management

This module provides functionality for discovering, caching, and invoking
tools on MCP servers with proper error handling and statistics tracking.
"""

import asyncio
import json
import logging
import time
import hashlib
from typing import Dict, List, Optional, Any, Tuple
from jsonschema import validate, ValidationError as JsonSchemaValidationError

logger = logging.getLogger(__name__)

class MCPToolManager:
    """
    Manages MCP tool discovery and caching
    """

    def __init__(self, connection_manager):
        self.connection_manager = connection_manager
        self.tools_cache = {}      # server_id -> [tools]
        self.tool_metadata = {}    # tool_key -> metadata
        self.cache_lock = asyncio.Lock()
        self.cache_ttl = 300       # 5 minutes cache TTL

    async def discover_tools(self, server_id: str) -> List[Dict[str, Any]]:
        """
        Discover available tools from MCP server

        Args:
            server_id: Server identifier

        Returns:
            List of tool dictionaries
        """
        try:
            logger.info(f"Discovering tools from MCP server: {server_id}")

            # Check cache first
            cached_tools = await self._get_cached_tools(server_id)
            if cached_tools:
                logger.info(f"Using cached tools for server {server_id}")
                return cached_tools

            # Fetch from server
            tools = await self._fetch_tools_from_server(server_id)

            if tools:
                await self._cache_tools(server_id, tools)
                logger.info(f"Discovered {len(tools)} tools from server {server_id}")
                return tools
            else:
                logger.warning(f"No tools found on server {server_id}")
                return []

        except Exception as e:
            logger.error(f"Error discovering tools from server {server_id}: {str(e)}")
            return []

    async def _get_cached_tools(self, server_id: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached tools if still valid"""
        async with self.cache_lock:
            if server_id in self.tools_cache:
                cached_data = self.tools_cache[server_id]
                if time.time() - cached_data['timestamp'] < self.cache_ttl:
                    return cached_data['tools']
        return None

    async def _cache_tools(self, server_id: str, tools: List[Dict[str, Any]]):
        """Cache tools with timestamp"""
        async with self.cache_lock:
            self.tools_cache[server_id] = {
                'tools': tools,
                'timestamp': time.time()
            }

            # Update tool metadata
            for tool in tools:
                tool_key = f"{server_id}:{tool['name']}"
                self.tool_metadata[tool_key] = {
                    'server_id': server_id,
                    'tool_name': tool['name'],
                    'schema': tool.get('schema'),
                    'description': tool.get('description'),
                    'capabilities': tool.get('capabilities', []),
                    'category': tool.get('category', 'general'),
                    'last_updated': time.time()
                }

    async def _fetch_tools_from_server(self, server_id: str) -> List[Dict[str, Any]]:
        """
        Fetch tools from MCP server using MCP protocol

        Implements the actual MCP tools/list protocol call
        """
        try:
            from .connection import MCPConnectionManager

            # Get connection manager
            if not hasattr(self, 'connection_manager') or self.connection_manager is None:
                # Create connection manager if not available
                self.connection_manager = MCPConnectionManager()

            # Send MCP tools/list request
            mcp_request = {
                "jsonrpc": "2.0",
                "id": f"tools_list_{int(time.time() * 1000)}",
                "method": "tools/list"
            }

            # Send request via connection manager
            response = await self.connection_manager.send_request(server_id, mcp_request)

            if not response:
                logger.warning(f"No response from MCP server {server_id}")
                return []

            # Parse MCP response
            if response.get('jsonrpc') == '2.0' and 'result' in response:
                tools = response['result'].get('tools', [])
                logger.info(f"Successfully fetched {len(tools)} tools from MCP server {server_id}")
                return tools
            elif 'error' in response:
                error = response['error']
                logger.error(f"MCP server {server_id} returned error: {error}")
                return []
            else:
                logger.error(f"Invalid MCP response from server {server_id}: {response}")
                return []

        except Exception as e:
            logger.error(f"Error fetching tools from server {server_id}: {str(e)}")
            # Fallback to cached tools if available
            return self.tool_metadata.get(server_id, {}).get('tools', [])

    async def refresh_tools_cache(self, server_id: str) -> bool:
        """
        Refresh tools cache for specific server

        Args:
            server_id: Server identifier

        Returns:
            bool: True if refresh successful
        """
        try:
            logger.info(f"Refreshing tools cache for server: {server_id}")

            # Clear existing cache
            async with self.cache_lock:
                if server_id in self.tools_cache:
                    del self.tools_cache[server_id]

            # Re-fetch tools
            tools = await self.discover_tools(server_id)
            return len(tools) > 0

        except Exception as e:
            logger.error(f"Error refreshing tools cache for server {server_id}: {str(e)}")
            return False

    def search_tools(self, query: str, capability_filter: Optional[str] = None,
                    category_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Search for tools by name, description, or capabilities

        Args:
            query: Search query
            capability_filter: Filter by capability
            category_filter: Filter by category

        Returns:
            List of matching tools
        """
        query_lower = query.lower()
        matching_tools = []

        for tool_key, metadata in self.tool_metadata.items():
            # Text search
            if (query_lower in metadata['tool_name'].lower() or
                (metadata['description'] and query_lower in metadata['description'].lower())):

                # Capability filter
                if capability_filter:
                    if capability_filter not in metadata['capabilities']:
                        continue

                # Category filter
                if category_filter:
                    if metadata['category'] != category_filter:
                        continue

                matching_tools.append({
                    'tool_key': tool_key,
                    'server_id': metadata['server_id'],
                    'name': metadata['tool_name'],
                    'description': metadata['description'],
                    'schema': metadata['schema'],
                    'capabilities': metadata['capabilities'],
                    'category': metadata['category']
                })

        return matching_tools

    def get_tool_metadata(self, server_id: str, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a specific tool

        Args:
            server_id: Server identifier
            tool_name: Tool name

        Returns:
            Tool metadata or None if not found
        """
        tool_key = f"{server_id}:{tool_name}"
        return self.tool_metadata.get(tool_key)

    def get_all_capabilities(self) -> List[str]:
        """Get list of all available capabilities across all tools"""
        capabilities = set()
        for metadata in self.tool_metadata.values():
            capabilities.update(metadata['capabilities'])
        return sorted(list(capabilities))

    def get_all_categories(self) -> List[str]:
        """Get list of all tool categories"""
        categories = set()
        for metadata in self.tool_metadata.values():
            categories.add(metadata['category'])
        return sorted(list(categories))

    async def clear_cache(self, server_id: Optional[str] = None):
        """
        Clear tools cache

        Args:
            server_id: Specific server to clear, or None to clear all
        """
        async with self.cache_lock:
            if server_id:
                if server_id in self.tools_cache:
                    del self.tools_cache[server_id]
                # Clear related metadata
                keys_to_remove = [k for k in self.tool_metadata.keys()
                                if self.tool_metadata[k]['server_id'] == server_id]
                for key in keys_to_remove:
                    del self.tool_metadata[key]
            else:
                self.tools_cache.clear()
                self.tool_metadata.clear()

class MCPToolInvoker:
    """
    Handles invocation of MCP tools with proper error handling and retries
    """

    def __init__(self, tool_manager: MCPToolManager, connection_manager):
        self.tool_manager = tool_manager
        self.connection_manager = connection_manager
        self.active_calls = {}  # call_id -> call_info
        self.call_history = []
        self.max_retries = 3
        self.call_timeout = 30

    async def invoke_tool(self, tool_name: str, arguments: Dict[str, Any],
                         context: Dict[str, Any], server_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Invoke a tool on MCP server

        Args:
            tool_name: Name of the tool to invoke
            arguments: Tool arguments
            context: Call context information
            server_id: Server ID (if None, will search for tool)

        Returns:
            Dict containing tool result or error information
        """
        call_id = f"{tool_name}_{int(time.time() * 1000)}"
        start_time = time.time()

        try:
            # Find tool if server_id not provided
            if not server_id:
                tool_metadata = self._find_tool(tool_name)
                if not tool_metadata:
                    return {
                        'success': False,
                        'error': f'Tool "{tool_name}" not found',
                        'call_id': call_id
                    }
                server_id = tool_metadata['server_id']
            else:
                tool_metadata = self.tool_manager.get_tool_metadata(server_id, tool_name)
                if not tool_metadata:
                    return {
                        'success': False,
                        'error': f'Tool "{tool_name}" not found on server {server_id}',
                        'call_id': call_id
                    }

            # Validate arguments against tool schema
            validation_result = self._validate_arguments(tool_metadata, arguments)
            if not validation_result['valid']:
                return {
                    'success': False,
                    'error': f'Invalid arguments: {validation_result["error"]}',
                    'call_id': call_id,
                    'validation_errors': validation_result['errors']
                }

            # Record call start
            self.active_calls[call_id] = {
                'tool_name': tool_name,
                'server_id': server_id,
                'arguments': arguments,
                'start_time': start_time,
                'context': context
            }

            # Execute tool with retries
            result = await self._execute_tool_with_retry(
                server_id, tool_name, arguments, context, call_id
            )

            # Record completion
            response_time = int((time.time() - start_time) * 1000)
            self._record_call_completion(call_id, result, response_time)

            return result

        except Exception as e:
            logger.error(f"Error invoking tool {tool_name}: {str(e)}")
            response_time = int((time.time() - start_time) * 1000)

            error_result = {
                'success': False,
                'error': str(e),
                'call_id': call_id,
                'response_time_ms': response_time
            }

            self._record_call_completion(call_id, error_result, response_time)
            return error_result

        finally:
            # Clean up active call
            if call_id in self.active_calls:
                del self.active_calls[call_id]

    def _find_tool(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Find tool by name across all servers"""
        for metadata in self.tool_manager.tool_metadata.values():
            if metadata['tool_name'] == tool_name:
                return metadata
        return None

    def _validate_arguments(self, tool_metadata: Dict[str, Any],
                           arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate arguments against tool schema

        Args:
            tool_metadata: Tool metadata including schema
            arguments: Arguments to validate

        Returns:
            Validation result
        """
        try:
            schema = tool_metadata.get('schema')
            if not schema:
                return {'valid': True, 'errors': []}

            # Validate using jsonschema
            validate(instance=arguments, schema=schema)
            return {'valid': True, 'errors': []}

        except JsonSchemaValidationError as e:
            return {
                'valid': False,
                'error': str(e.message),
                'errors': [str(e.message)]
            }
        except Exception as e:
            return {
                'valid': False,
                'error': f'Schema validation error: {str(e)}',
                'errors': [f'Schema validation error: {str(e)}']
            }

    async def _execute_tool_with_retry(self, server_id: str, tool_name: str,
                                     arguments: Dict[str, Any], context: Dict[str, Any],
                                     call_id: str) -> Dict[str, Any]:
        """Execute tool with retry logic"""
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                if attempt > 0:
                    logger.info(f"Retrying tool {tool_name} (attempt {attempt + 1})")
                    await asyncio.sleep(1 * attempt)  # Exponential backoff

                result = await self._execute_single_call(
                    server_id, tool_name, arguments, context, self.call_timeout
                )

                if result.get('success'):
                    return result
                else:
                    last_error = result.get('error', 'Unknown error')
                    logger.warning(f"Tool {tool_name} failed on attempt {attempt + 1}: {last_error}")

            except asyncio.TimeoutError:
                last_error = f"Tool call timeout after {self.call_timeout} seconds"
                logger.error(f"Tool {tool_name} timeout on attempt {attempt + 1}")
            except Exception as e:
                last_error = str(e)
                logger.error(f"Tool {tool_name} error on attempt {attempt + 1}: {last_error}")

        # All retries failed
        return {
            'success': False,
            'error': f'Tool execution failed after {self.max_retries + 1} attempts. Last error: {last_error}',
            'call_id': call_id,
            'attempts': self.max_retries + 1
        }

    async def _execute_single_call(self, server_id: str, tool_name: str,
                                 arguments: Dict[str, Any], context: Dict[str, Any],
                                 timeout: int) -> Dict[str, Any]:
        """
        Execute single tool call with timeout using MCP protocol

        Implements the actual MCP tools/call protocol call
        """
        try:
            # Get connection manager
            if not hasattr(self, 'connection_manager') or self.connection_manager is None:
                from .connection import MCPConnectionManager
                self.connection_manager = MCPConnectionManager()

            # Prepare MCP tools/call request
            mcp_request = {
                "jsonrpc": "2.0",
                "id": f"tools_call_{int(time.time() * 1000)}",
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                }
            }

            # Add context to request if available
            if context:
                mcp_request["params"]["_context"] = context

            # Send request with timeout
            response = await asyncio.wait_for(
                self.connection_manager.send_request(server_id, mcp_request),
                timeout=timeout
            )

            if not response:
                return {
                    'success': False,
                    'error': 'No response from MCP server',
                    'tool_name': tool_name,
                    'server_id': server_id
                }

            # Parse MCP response
            if response.get('jsonrpc') == '2.0' and 'result' in response:
                result_data = response['result']

                # Handle different response formats
                if isinstance(result_data, dict):
                    # Structured result
                    return {
                        'success': True,
                        'result': result_data.get('content', result_data),
                        'tool_name': tool_name,
                        'server_id': server_id,
                        'arguments': arguments,
                        'metadata': {
                            'isError': result_data.get('isError', False),
                            'mcp_result': result_data
                        }
                    }
                else:
                    # Simple string result
                    return {
                        'success': True,
                        'result': str(result_data),
                        'tool_name': tool_name,
                        'server_id': server_id,
                        'arguments': arguments
                    }

            elif 'error' in response:
                error = response['error']
                error_message = error.get('message', 'Unknown MCP error')
                error_code = error.get('code', -1)

                return {
                    'success': False,
                    'error': error_message,
                    'error_code': error_code,
                    'tool_name': tool_name,
                    'server_id': server_id,
                    'arguments': arguments,
                    'mcp_error': error
                }
            else:
                return {
                    'success': False,
                    'error': f'Invalid MCP response format: {response}',
                    'tool_name': tool_name,
                    'server_id': server_id
                }

        except asyncio.TimeoutError:
            return {
                'success': False,
                'error': f'Tool call timeout after {timeout} seconds',
                'tool_name': tool_name,
                'server_id': server_id
            }
        except Exception as e:
            logger.error(f"Error executing tool {tool_name} on server {server_id}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'tool_name': tool_name,
                'server_id': server_id
            }

    def _record_call_completion(self, call_id: str, result: Dict[str, Any], response_time: int):
        """Record completion of tool call"""
        call_info = self.active_calls.get(call_id, {})

        call_record = {
            'call_id': call_id,
            'tool_name': call_info.get('tool_name'),
            'server_id': call_info.get('server_id'),
            'arguments': call_info.get('arguments'),
            'success': result.get('success', False),
            'result': result.get('result') if result.get('success') else result.get('error'),
            'response_time_ms': response_time,
            'timestamp': time.time()
        }

        self.call_history.append(call_record)

        # Keep only last 1000 calls in memory
        if len(self.call_history) > 1000:
            self.call_history = self.call_history[-1000:]

    def get_active_calls(self) -> List[Dict[str, Any]]:
        """Get list of currently active tool calls"""
        return [
            {
                'call_id': call_id,
                'tool_name': info['tool_name'],
                'server_id': info['server_id'],
                'duration_ms': int((time.time() - info['start_time']) * 1000)
            }
            for call_id, info in self.active_calls.items()
        ]

    def get_call_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent call history"""
        return self.call_history[-limit:]

    def get_tool_stats(self) -> Dict[str, Any]:
        """Get tool invocation statistics"""
        if not self.call_history:
            return {}

        total_calls = len(self.call_history)
        successful_calls = sum(1 for call in self.call_history if call['success'])

        avg_response_time = sum(call['response_time_ms'] for call in self.call_history) / total_calls

        tool_usage = {}
        for call in self.call_history:
            tool_name = call['tool_name']
            if tool_name not in tool_usage:
                tool_usage[tool_name] = {'calls': 0, 'successes': 0}
            tool_usage[tool_name]['calls'] += 1
            if call['success']:
                tool_usage[tool_name]['successes'] += 1

        return {
            'total_calls': total_calls,
            'successful_calls': successful_calls,
            'success_rate': successful_calls / total_calls * 100,
            'avg_response_time_ms': round(avg_response_time, 2),
            'tool_usage': tool_usage,
            'active_calls': len(self.active_calls)
        }