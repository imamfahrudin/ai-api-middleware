"""
Main MCP Client implementation

This module provides the core MCP client functionality for connecting
to MCP servers and managing tool interactions.
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Optional, Any, Tuple
import aiohttp
import websockets
from urllib.parse import urlparse

from .connection import MCPConnectionManager
from .tools import MCPToolManager, MCPToolInvoker
from .translator import MCPIntentDetector, MCPRequestTranslator
from .orchestrator import MCPResponseOrchestrator

logger = logging.getLogger(__name__)

class MCPClient:
    """
    Main MCP Client class that handles communication with MCP servers

    This client provides a high-level interface for:
    - Connecting to MCP servers
    - Discovering and invoking tools
    - Managing connections and sessions
    - Translating requests and responses
    """

    def __init__(self, server_config: Dict[str, Any]):
        """
        Initialize MCP Client

        Args:
            server_config: Configuration dictionary containing:
                - url: MCP server URL
                - auth_type: Authentication type ('none', 'bearer', 'api_key', 'oauth')
                - auth_credentials: Authentication credentials
                - name: Human-readable server name
                - timeout: Connection timeout in seconds
                - max_retries: Maximum retry attempts
        """
        self.server_config = server_config
        self.server_id = server_config.get('id', server_config.get('name', 'unknown'))
        self.server_url = server_config['url']
        self.auth_type = server_config.get('auth_type', 'none')
        self.auth_credentials = server_config.get('auth_credentials', {})
        self.name = server_config.get('name', self.server_url)
        self.timeout = server_config.get('timeout', 30)
        self.max_retries = server_config.get('max_retries', 3)

        # Initialize components
        self.connection_manager = MCPConnectionManager()
        self.tool_manager = MCPToolManager(self.connection_manager)
        self.tool_invoker = MCPToolInvoker(self.tool_manager, self.connection_manager)
        self.intent_detector = MCPIntentDetector(self.tool_manager)
        self.request_translator = MCPRequestTranslator(self.intent_detector, self.tool_manager)
        self.response_orchestrator = MCPResponseOrchestrator(self)

        # Client state
        self.is_connected = False
        self.connection_time = None
        self.last_health_check = None
        self.health_status = 'unknown'
        self.tools_cache = {}
        self.session_data = {}

        logger.info(f"MCP Client initialized for server: {self.name} ({self.server_url})")

    async def connect(self) -> bool:
        """
        Establish connection to MCP server

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            logger.info(f"Connecting to MCP server: {self.name}")

            # Parse URL to determine connection type
            parsed_url = urlparse(self.server_url)

            if parsed_url.scheme in ['ws', 'wss']:
                # WebSocket connection
                connection = await self.connection_manager.connect_websocket(
                    self.server_url,
                    self.auth_type,
                    self.auth_credentials,
                    self.timeout
                )
            else:
                # HTTP connection
                connection = await self.connection_manager.connect_http(
                    self.server_url,
                    self.auth_type,
                    self.auth_credentials,
                    self.timeout
                )

            if connection:
                self.is_connected = True
                self.connection_time = time.time()
                self.health_status = 'connected'

                # Discover available tools
                await self._discover_tools()

                logger.info(f"Successfully connected to MCP server: {self.name}")
                return True
            else:
                logger.error(f"Failed to connect to MCP server: {self.name}")
                self.health_status = 'connection_failed'
                return False

        except Exception as e:
            logger.error(f"Error connecting to MCP server {self.name}: {str(e)}")
            self.health_status = 'error'
            return False

    async def disconnect(self):
        """Clean shutdown of MCP connection"""
        try:
            logger.info(f"Disconnecting from MCP server: {self.name}")
            await self.connection_manager.disconnect(self.server_id)
            self.is_connected = False
            self.health_status = 'disconnected'
            logger.info(f"Successfully disconnected from MCP server: {self.name}")
        except Exception as e:
            logger.error(f"Error disconnecting from MCP server {self.name}: {str(e)}")

    async def _discover_tools(self) -> bool:
        """
        Discover available tools from MCP server

        Returns:
            bool: True if tool discovery successful, False otherwise
        """
        try:
            logger.info(f"Discovering tools from MCP server: {self.name}")

            tools = await self.tool_manager.discover_tools(self.server_id)

            if tools:
                self.tools_cache = {tool['name']: tool for tool in tools}
                logger.info(f"Discovered {len(tools)} tools from MCP server: {self.name}")
                return True
            else:
                logger.warning(f"No tools discovered from MCP server: {self.name}")
                return False

        except Exception as e:
            logger.error(f"Error discovering tools from MCP server {self.name}: {str(e)}")
            return False

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on MCP server

        Returns:
            Dict containing health status information
        """
        try:
            if not self.is_connected:
                return {
                    'status': 'disconnected',
                    'server': self.name,
                    'url': self.server_url,
                    'last_check': time.time()
                }

            start_time = time.time()
            is_healthy = await self.connection_manager.health_check(self.server_id)
            response_time = int((time.time() - start_time) * 1000)

            self.last_health_check = time.time()
            self.health_status = 'healthy' if is_healthy else 'unhealthy'

            return {
                'status': 'healthy' if is_healthy else 'unhealthy',
                'server': self.name,
                'url': self.server_url,
                'response_time_ms': response_time,
                'tools_count': len(self.tools_cache),
                'connection_time': self.connection_time,
                'last_check': self.last_health_check
            }

        except Exception as e:
            logger.error(f"Health check failed for MCP server {self.name}: {str(e)}")
            self.health_status = 'error'
            return {
                'status': 'error',
                'server': self.name,
                'url': self.server_url,
                'error': str(e),
                'last_check': time.time()
            }

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any],
                       context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Call a tool on the MCP server

        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments
            context: Optional context information

        Returns:
            Dict containing tool result or error information
        """
        try:
            if not self.is_connected:
                return {
                    'success': False,
                    'error': 'Not connected to MCP server',
                    'server': self.name
                }

            if tool_name not in self.tools_cache:
                return {
                    'success': False,
                    'error': f'Tool "{tool_name}" not found on server',
                    'available_tools': list(self.tools_cache.keys()),
                    'server': self.name
                }

            logger.info(f"Calling tool '{tool_name}' on MCP server: {self.name}")

            result = await self.tool_invoker.invoke_tool(
                tool_name=tool_name,
                arguments=arguments,
                context=context or {}
            )

            if result.get('success'):
                logger.info(f"Tool '{tool_name}' executed successfully on server: {self.name}")
            else:
                logger.warning(f"Tool '{tool_name}' failed on server {self.name}: {result.get('error', 'Unknown error')}")

            return result

        except Exception as e:
            logger.error(f"Error calling tool '{tool_name}' on MCP server {self.name}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'server': self.name,
                'tool': tool_name
            }

    def get_available_tools(self) -> List[Dict[str, Any]]:
        """
        Get list of available tools

        Returns:
            List of available tool dictionaries
        """
        return list(self.tools_cache.values())

    def get_tool_info(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific tool

        Args:
            tool_name: Name of the tool

        Returns:
            Tool information dictionary or None if not found
        """
        return self.tools_cache.get(tool_name)

    async def refresh_tools(self) -> bool:
        """
        Refresh the tools cache from MCP server

        Returns:
            bool: True if refresh successful, False otherwise
        """
        try:
            logger.info(f"Refreshing tools cache from MCP server: {self.name}")
            return await self._discover_tools()
        except Exception as e:
            logger.error(f"Error refreshing tools from MCP server {self.name}: {str(e)}")
            return False

    def get_connection_info(self) -> Dict[str, Any]:
        """
        Get connection information

        Returns:
            Dict containing connection details
        """
        return {
            'server_name': self.name,
            'server_url': self.server_url,
            'server_id': self.server_id,
            'is_connected': self.is_connected,
            'health_status': self.health_status,
            'connection_time': self.connection_time,
            'last_health_check': self.last_health_check,
            'available_tools_count': len(self.tools_cache),
            'auth_type': self.auth_type
        }