"""
MCP Integration Module for AI API Middleware

This module provides the integration layer between the existing proxy logic
and the MCP client, enabling seamless tool usage for AI requests.
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Optional, Any, Union
from flask import request, g
import threading

from app.database import KeyManager
from app.mcp_client import MCPClient, MCPIntentDetector, MCPRequestTranslator, MCPResponseOrchestrator
from app.mcp_sessions import get_mcp_session_manager
from app.logging_utils import add_log_entry

logger = logging.getLogger(__name__)

class MCPIntegrationManager:
    """
    Manages MCP integration with the AI API middleware
    """

    def __init__(self, key_manager: KeyManager):
        self.key_manager = key_manager
        self.mcp_clients: Dict[int, MCPClient] = {}  # server_id -> MCPClient
        self.intent_detector: Optional[MCPIntentDetector] = None
        self.request_translator: Optional[MCPRequestTranslator] = None
        self.response_orchestrator: Optional[MCPResponseOrchestrator] = None
        self.is_enabled = False
        self._lock = threading.Lock()
        self._init_clients()

    def _init_clients(self):
        """Initialize MCP clients from database configuration"""
        try:
            # Check if MCP is enabled in settings
            mcp_enabled = self.key_manager.get_setting('mcp_enabled', 'false').lower() == 'true'
            if not mcp_enabled:
                logger.info("MCP is disabled in settings")
                return

            with self._lock:
                # Get active MCP servers from database
                servers = self.key_manager.get_mcp_servers(status_filter='Active')

                if not servers:
                    logger.info("No active MCP servers configured")
                    self.is_enabled = False
                    return

                # Initialize clients for each server
                for server in servers:
                    try:
                        client = MCPClient({
                            'id': server['id'],
                            'name': server['name'],
                            'url': server['url'],
                            'auth_type': server['auth_type'],
                            'auth_credentials': server['auth_credentials'],
                            'timeout': int(self.key_manager.get_setting('mcp_timeout', '30')),
                            'max_retries': 3
                        })
                        self.mcp_clients[server['id']] = client
                        logger.info(f"Initialized MCP client for server: {server['name']}")

                    except Exception as e:
                        logger.error(f"Failed to initialize MCP client for server {server['name']}: {str(e)}")

                # Initialize MCP components if we have clients
                if self.mcp_clients:
                    # Get tools from all servers for intent detection
                    self._refresh_tools_cache()

                    # Initialize components (we'll pass a mock tool manager for now)
                    from app.mcp_client.tools import MCPToolManager
                    mock_tool_manager = MCPToolManager(None)  # We'll populate this with cached tools

                    # Populate mock tool manager with cached tools
                    all_tools = self.key_manager.get_mcp_tools()
                    for tool in all_tools:
                        tool_key = f"{tool['server_id']}:{tool['tool_name']}"
                        mock_tool_manager.tool_metadata[tool_key] = {
                            'server_id': tool['server_id'],
                            'tool_name': tool['tool_name'],
                            'schema': tool['tool_schema'],
                            'description': tool['description'],
                            'capabilities': tool['capabilities'],
                            'category': tool['category'],
                            'last_updated': time.time()
                        }

                    self.intent_detector = MCPIntentDetector(mock_tool_manager)
                    self.request_translator = MCPRequestTranslator(self.intent_detector, mock_tool_manager)
                    self.response_orchestrator = MCPResponseOrchestrator(self)
                    self.is_enabled = True

                    logger.info(f"MCP integration enabled with {len(self.mcp_clients)} servers")
                else:
                    self.is_enabled = False

        except Exception as e:
            logger.error(f"Error initializing MCP integration: {str(e)}")
            self.is_enabled = False

    def _refresh_tools_cache(self):
        """Refresh tools cache from database"""
        try:
            # This would normally be done by connecting to MCP servers
            # For now, we'll load from database cache
            all_tools = self.key_manager.get_mcp_tools()
            logger.info(f"Loaded {len(all_tools)} tools from database cache")
        except Exception as e:
            logger.error(f"Error refreshing tools cache: {str(e)}")

    async def process_request_with_mcp(self, original_request: str, request_data: Dict[str, Any],
                                     session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Process request through MCP pipeline if tools are needed

        Args:
            original_request: The original user request text
            request_data: Request data and context
            session_id: Optional session ID for multi-turn conversations

        Returns:
            Enhanced response with tool results if applicable
        """
        if not self.is_enabled:
            return {'requires_mcp': False, 'reason': 'MCP disabled'}

        try:
            # Get session manager
            session_manager = get_mcp_session_manager()
            session = None

            # Get or create session
            if session_manager and self.key_manager.get_setting('mcp_enable_usage_tracking', 'true').lower() == 'true':
                if session_id:
                    session = session_manager.get_session(session_id)

                if not session:
                    # Create new session
                    user_context = {
                        'ip_address': request_data.get('ip_address'),
                        'user_agent': request_data.get('user_agent'),
                        'request_id': request_data.get('request_id')
                    }
                    session_id = session_manager.create_session(user_context)
                    session = session_manager.get_session(session_id)

                # Add conversation context to analysis
                if session:
                    conversation_summary = session_manager.get_conversation_summary(session_id, max_turns=3)
                    request_data['conversation_context'] = conversation_summary

            # Detect if request needs MCP tools
            mcp_analysis = self.intent_detector.analyze_request(original_request, request_data.get('conversation_context'))

            # Enhance analysis with session context
            if session:
                # Check previous tool usage for context
                recent_tools = session_manager.get_tool_context(session_id)
                if recent_tools:
                    mcp_analysis['recent_tool_context'] = recent_tools[:3]  # Last 3 tool usages

            if not mcp_analysis.get('requires_tools', False):
                return {
                    'requires_mcp': False,
                    'reason': 'No tools needed',
                    'session_id': session_id
                }

            add_log_entry(f"MCP: Tools detected for request - {mcp_analysis.get('recommended_tools', [])[:2]}", "text-blue-400")

            # Translate to MCP request with session context
            mcp_request = self.request_translator.translate_to_mcp_request(
                original_request,
                mcp_analysis.get('recommended_tools', []),
                mcp_analysis.get('extracted_arguments', {})
            )

            # Add session preferences to request
            if session:
                mcp_request['session_preferences'] = session.get('preferences', {})

            # Execute tools and orchestrate response
            result = await self.response_orchestrator.orchestrate_response(
                original_request,
                {**mcp_analysis, **mcp_request}
            )

            # Log usage statistics
            self._log_mcp_usage(result)

            # Update session with conversation turn
            if session and session_manager:
                session_manager.add_conversation_turn(
                    session_id=session_id,
                    user_message=original_request,
                    ai_response=result.get('response', ''),
                    tool_results=result.get('tool_results', []),
                    metadata={
                        'mcp_analysis': mcp_analysis,
                        'processing_time': result.get('metadata', {}).get('response_time_ms'),
                        'tool_count': len(result.get('tool_results', []))
                    }
                )

            return {
                'requires_mcp': True,
                'response': result.get('response'),
                'tool_results': result.get('tool_results', []),
                'metadata': result.get('metadata', {}),
                'session_id': session_id
            }

        except Exception as e:
            logger.error(f"Error in MCP processing: {str(e)}")
            add_log_entry(f"MCP: Processing error - {str(e)}", "text-red-500")
            return {
                'requires_mcp': False,
                'error': str(e),
                'fallback_to_ai': True,
                'session_id': session_id
            }

    def _log_mcp_usage(self, result: Dict[str, Any]):
        """Log MCP usage for statistics"""
        try:
            if not self.key_manager.get_setting('mcp_enable_usage_tracking', 'true').lower() == 'true':
                return

            metadata = result.get('metadata', {})
            tool_results = result.get('tool_results', [])

            for tool_result in tool_results:
                if tool_result.get('success'):
                    server_id = tool_result.get('server_id')
                    tool_name = tool_result.get('tool_name')

                    # Record usage in database
                    self.key_manager.record_mcp_tool_call(
                        server_id=server_id,
                        tool_name=tool_name,
                        arguments=tool_result.get('arguments', {}),
                        result=tool_result.get('result'),
                        success=True,
                        response_time=metadata.get('response_time_ms', 0)
                    )

        except Exception as e:
            logger.error(f"Error logging MCP usage: {str(e)}")

    def get_client_for_server(self, server_id: int) -> Optional[MCPClient]:
        """Get MCP client for specific server"""
        with self._lock:
            return self.mcp_clients.get(server_id)

    def get_all_clients(self) -> List[MCPClient]:
        """Get all MCP clients"""
        with self._lock:
            return list(self.mcp_clients.values())

    def reload_configuration(self):
        """Reload MCP configuration from database"""
        logger.info("Reloading MCP configuration")

        # Disconnect existing clients
        with self._lock:
            for client in self.mcp_clients.values():
                try:
                    asyncio.create_task(client.disconnect())
                except:
                    pass
            self.mcp_clients.clear()

        # Reinitialize
        self._init_clients()

    async def health_check_all_servers(self) -> Dict[int, Dict[str, Any]]:
        """Perform health check on all MCP servers"""
        health_results = {}

        for server_id, client in self.mcp_clients.items():
            try:
                health_info = await client.health_check()
                health_results[server_id] = health_info

                # Record health check in database
                self.key_manager.record_mcp_health_check(
                    server_id=server_id,
                    status=health_info.get('status', 'unknown'),
                    response_time=health_info.get('response_time_ms'),
                    error_message=health_info.get('error')
                )

            except Exception as e:
                health_results[server_id] = {
                    'status': 'error',
                    'error': str(e),
                    'server_name': client.name
                }
                logger.error(f"Health check failed for server {server_id}: {str(e)}")

        return health_results

    def get_statistics(self) -> Dict[str, Any]:
        """Get MCP integration statistics"""
        try:
            # Get usage stats from database
            usage_stats = self.key_manager.get_mcp_usage_stats(days=7)

            # Get server information
            servers = self.key_manager.get_mcp_servers()
            active_servers = [s for s in servers if s['status'] == 'Active']

            # Get tool information
            tools = self.key_manager.get_mcp_tools()

            return {
                'enabled': self.is_enabled,
                'servers': {
                    'total': len(servers),
                    'active': len(active_servers),
                    'connected': len(self.mcp_clients)
                },
                'tools': {
                    'total': len(tools),
                    'by_category': self._group_tools_by_category(tools)
                },
                'usage': {
                    'last_7_days': len(usage_stats),
                    'total_calls': sum(s.get('total_calls', 0) for s in usage_stats),
                    'success_rate': self._calculate_success_rate(usage_stats)
                },
                'performance': {
                    'avg_response_time': self._calculate_avg_response_time(usage_stats)
                }
            }

        except Exception as e:
            logger.error(f"Error getting MCP statistics: {str(e)}")
            return {'error': str(e), 'enabled': self.is_enabled}

    def _group_tools_by_category(self, tools: List[Dict[str, Any]]) -> Dict[str, int]:
        """Group tools by category"""
        categories = {}
        for tool in tools:
            category = tool.get('category', 'general')
            categories[category] = categories.get(category, 0) + 1
        return categories

    def _calculate_success_rate(self, usage_stats: List[Dict[str, Any]]) -> float:
        """Calculate overall success rate"""
        if not usage_stats:
            return 0.0

        total_calls = sum(s.get('total_calls', 0) for s in usage_stats)
        successful_calls = sum(s.get('successful_calls', 0) for s in usage_stats)

        return (successful_calls / total_calls * 100) if total_calls > 0 else 0.0

    def _calculate_avg_response_time(self, usage_stats: List[Dict[str, Any]]) -> float:
        """Calculate average response time"""
        if not usage_stats:
            return 0.0

        response_times = [s.get('avg_response_time', 0) for s in usage_stats if s.get('avg_response_time')]
        return sum(response_times) / len(response_times) if response_times else 0.0

# Global MCP integration manager instance
mcp_integration_manager: Optional[MCPIntegrationManager] = None

def initialize_mcp_integration(key_manager: KeyManager):
    """Initialize MCP integration manager"""
    global mcp_integration_manager
    mcp_integration_manager = MCPIntegrationManager(key_manager)

def get_mcp_integration() -> Optional[MCPIntegrationManager]:
    """Get global MCP integration manager"""
    return mcp_integration_manager

async def process_request_with_mcp_integration(request_text: str, request_data: Dict[str, Any],
                                                session_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Convenience function to process request with MCP integration

    This function can be called from the proxy logic to check if MCP tools
    should be used for a given request.

    Args:
        request_text: The request text
        request_data: Request data and context
        session_id: Optional session ID for multi-turn conversations

    Returns:
        MCP processing result
    """
    mcp_manager = get_mcp_integration()
    if not mcp_manager:
        return {'requires_mcp': False, 'reason': 'MCP not initialized'}

    return await mcp_manager.process_request_with_mcp(request_text, request_data, session_id)