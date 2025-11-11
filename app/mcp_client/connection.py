"""
MCP Connection Management

This module provides connection pooling and management for MCP servers,
supporting both HTTP and WebSocket connections with authentication.
"""

import asyncio
import json
import logging
import time
import weakref
from typing import Dict, Optional, Any, Union
import aiohttp
import websockets
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class MCPConnection:
    """
    Represents a single connection to an MCP server
    """

    def __init__(self, server_id: str, connection: Union[aiohttp.ClientSession, websockets.WebSocketClientProtocol]):
        self.server_id = server_id
        self.connection = connection
        self.created_at = time.time()
        self.last_used = time.time()
        self.is_active = True
        self.request_count = 0
        self.error_count = 0

    async def send_request(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Send request to MCP server"""
        self.last_used = time.time()
        self.request_count += 1

        try:
            if isinstance(self.connection, websockets.WebSocketClientProtocol):
                # WebSocket connection
                await self.connection.send(json.dumps(data))
                response = await self.connection.recv()
                return json.loads(response)
            else:
                # HTTP connection
                async with self.connection.post('/mcp', json=data) as resp:
                    return await resp.json()

        except Exception as e:
            self.error_count += 1
            raise e

    async def close(self):
        """Close the connection"""
        try:
            if isinstance(self.connection, websockets.WebSocketClientProtocol):
                await self.connection.close()
            else:
                await self.connection.close()
        except Exception as e:
            logger.error(f"Error closing connection for {self.server_id}: {str(e)}")
        finally:
            self.is_active = False

class MCPConnectionPool:
    """
    Connection pool for MCP server connections
    """

    def __init__(self, max_connections: int = 10, connection_timeout: int = 300):
        self.max_connections = max_connections
        self.connection_timeout = connection_timeout
        self.pools: Dict[str, list] = {}  # server_id -> [MCPConnection]
        self.active_connections: Dict[str, MCPConnection] = {}  # connection_id -> MCPConnection
        self.lock = asyncio.Lock()
        self.cleanup_task = None

        # Start cleanup task
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def get_connection(self, server_id: str, connection_factory) -> Optional[MCPConnection]:
        """
        Get a connection from the pool or create a new one

        Args:
            server_id: Server identifier
            connection_factory: Factory function to create new connections

        Returns:
            MCPConnection instance or None if failed
        """
        async with self.lock:
            # Check if pool exists for this server
            if server_id not in self.pools:
                self.pools[server_id] = []

            # Try to get existing connection from pool
            while self.pools[server_id]:
                connection = self.pools[server_id].pop()
                if connection.is_active:
                    self.active_connections[id(connection)] = connection
                    return connection
                else:
                    # Remove dead connection
                    if id(connection) in self.active_connections:
                        del self.active_connections[id(connection)]

            # Check if we can create new connection
            total_active = len(self.active_connections)
            if total_active >= self.max_connections:
                logger.warning(f"Connection pool exhausted for {server_id}")
                return None

            # Create new connection
            try:
                raw_connection = await connection_factory()
                if raw_connection:
                    connection = MCPConnection(server_id, raw_connection)
                    self.active_connections[id(connection)] = connection
                    return connection
            except Exception as e:
                logger.error(f"Failed to create connection for {server_id}: {str(e)}")
                return None

    async def release_connection(self, connection: MCPConnection):
        """
        Release a connection back to the pool

        Args:
            connection: Connection to release
        """
        async with self.lock:
            connection_id = id(connection)
            if connection_id in self.active_connections:
                # Check if connection is still healthy
                if (connection.is_active and
                    connection.error_count < 3 and
                    time.time() - connection.created_at < self.connection_timeout):

                    # Return to pool
                    if connection.server_id not in self.pools:
                        self.pools[connection.server_id] = []
                    self.pools[connection.server_id].append(connection)
                else:
                    # Close unhealthy connection
                    await connection.close()

                del self.active_connections[connection_id]

    async def close_all(self):
        """Close all connections in the pool"""
        async with self.lock:
            # Close active connections
            for connection in list(self.active_connections.values()):
                await connection.close()
            self.active_connections.clear()

            # Close pooled connections
            for pool in self.pools.values():
                for connection in pool:
                    await connection.close()
            self.pools.clear()

        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass

    async def _cleanup_loop(self):
        """Background task to cleanup expired connections"""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                await self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in connection cleanup loop: {str(e)}")

    async def _cleanup_expired(self):
        """Remove expired connections from pool"""
        async with self.lock:
            current_time = time.time()
            expired_connections = []

            for connection_id, connection in list(self.active_connections.items()):
                if (current_time - connection.created_at > self.connection_timeout or
                    not connection.is_active or
                    connection.error_count >= 3):
                    expired_connections.append(connection)

            for connection in expired_connections:
                await connection.close()
                if id(connection) in self.active_connections:
                    del self.active_connections[id(connection)]

            # Also cleanup pooled connections
            for server_id, pool in list(self.pools.items()):
                valid_connections = []
                for connection in pool:
                    if (connection.is_active and
                        connection.error_count < 3 and
                        current_time - connection.created_at < self.connection_timeout):
                        valid_connections.append(connection)
                    else:
                        await connection.close()
                self.pools[server_id] = valid_connections

    def get_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics"""
        total_pooled = sum(len(pool) for pool in self.pools.values())
        return {
            'active_connections': len(self.active_connections),
            'pooled_connections': total_pooled,
            'total_connections': len(self.active_connections) + total_pooled,
            'servers': list(self.pools.keys()),
            'max_connections': self.max_connections
        }

class MCPConnectionManager:
    """
    Manages connections to MCP servers with support for different auth types
    """

    def __init__(self, pool_size: int = 10):
        self.connection_pool = MCPConnectionPool(max_connections=pool_size)
        self.server_sessions: Dict[str, Dict[str, Any]] = {}
        self.active_websockets: Dict[str, websockets.WebSocketClientProtocol] = {}

    async def connect_http(self, url: str, auth_type: str, auth_credentials: Dict[str, Any],
                          timeout: int) -> Optional[aiohttp.ClientSession]:
        """
        Establish HTTP connection to MCP server

        Args:
            url: Server URL
            auth_type: Authentication type
            auth_credentials: Authentication credentials
            timeout: Connection timeout

        Returns:
            aiohttp.ClientSession or None if failed
        """
        try:
            # Configure authentication
            headers = {'Content-Type': 'application/json'}

            if auth_type == 'bearer':
                token = auth_credentials.get('token')
                if token:
                    headers['Authorization'] = f'Bearer {token}'
            elif auth_type == 'api_key':
                key = auth_credentials.get('key')
                key_header = auth_credentials.get('header', 'X-API-Key')
                if key:
                    headers[key_header] = key

            # Create session with timeout
            timeout_config = aiohttp.ClientTimeout(total=timeout)
            session = aiohttp.ClientSession(
                headers=headers,
                timeout=timeout_config,
                connector=aiohttp.TCPConnector(limit=10)
            )

            # Test connection
            async with session.get(url or '/health') as resp:
                if resp.status == 200:
                    return session
                else:
                    await session.close()
                    return None

        except Exception as e:
            logger.error(f"HTTP connection failed to {url}: {str(e)}")
            return None

    async def connect_websocket(self, url: str, auth_type: str, auth_credentials: Dict[str, Any],
                               timeout: int) -> Optional[websockets.WebSocketClientProtocol]:
        """
        Establish WebSocket connection to MCP server

        Args:
            url: WebSocket URL
            auth_type: Authentication type
            auth_credentials: Authentication credentials
            timeout: Connection timeout

        Returns:
            WebSocket connection or None if failed
        """
        try:
            # Prepare connection parameters
            extra_headers = {}

            if auth_type == 'bearer':
                token = auth_credentials.get('token')
                if token:
                    extra_headers['Authorization'] = f'Bearer {token}'
            elif auth_type == 'api_key':
                key = auth_credentials.get('key')
                key_header = auth_credentials.get('header', 'X-API-Key')
                if key:
                    extra_headers[key_header] = key

            # Connect with timeout
            connection = await asyncio.wait_for(
                websockets.connect(url, extra_headers=extra_headers),
                timeout=timeout
            )

            # Test connection with ping
            await connection.ping()
            return connection

        except Exception as e:
            logger.error(f"WebSocket connection failed to {url}: {str(e)}")
            return None

    async def disconnect(self, server_id: str):
        """
        Disconnect from MCP server

        Args:
            server_id: Server identifier
        """
        try:
            # Close WebSocket if exists
            if server_id in self.active_websockets:
                await self.active_websockets[server_id].close()
                del self.active_websockets[server_id]

            # Clean up session data
            if server_id in self.server_sessions:
                del self.server_sessions[server_id]

            logger.info(f"Disconnected from MCP server: {server_id}")

        except Exception as e:
            logger.error(f"Error disconnecting from {server_id}: {str(e)}")

    async def health_check(self, server_id: str) -> bool:
        """
        Perform health check on MCP server

        Args:
            server_id: Server identifier

        Returns:
            bool: True if server is healthy, False otherwise
        """
        try:
            # For now, just check if we have active connections
            # In a full implementation, this would send a health check request
            return server_id in self.server_sessions or server_id in self.active_websockets

        except Exception as e:
            logger.error(f"Health check failed for {server_id}: {str(e)}")
            return False

    async def send_request(self, server_id: str, request_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Send request to MCP server using JSON-RPC 2.0 protocol

        Args:
            server_id: Server identifier
            request_data: Request data (must follow MCP JSON-RPC format)

        Returns:
            Response data or None if failed
        """
        try:
            # Validate request format
            if not isinstance(request_data, dict):
                raise ValueError("Request data must be a dictionary")

            if 'method' not in request_data:
                raise ValueError("Request must contain 'method' field")

            # Get connection for this server
            connection = await self.connection_pool.get_connection(
                server_id,
                lambda: self._create_connection_for_server(server_id)
            )

            if not connection:
                logger.error(f"Failed to get connection for server {server_id}")
                return None

            # Send request
            response = await connection.send_request(request_data)

            # Return connection to pool
            await self.connection_pool.release_connection(connection)

            return response

        except Exception as e:
            logger.error(f"Failed to send request to {server_id}: {str(e)}")
            return None

    async def _create_connection_for_server(self, server_id: str):
        """Create a connection for a specific server"""
        try:
            # This would need server information from database or config
            # For now, return None to indicate no connection available
            # In a full implementation, you'd look up server details from database
            logger.warning(f"Cannot create connection for server {server_id} - server details not available")
            return None

        except Exception as e:
            logger.error(f"Error creating connection for server {server_id}: {str(e)}")
            return None

    async def cleanup(self):
        """Cleanup all connections"""
        await self.connection_pool.close_all()

        # Close remaining websockets
        for ws in self.active_websockets.values():
            await ws.close()
        self.active_websockets.clear()

        self.server_sessions.clear()