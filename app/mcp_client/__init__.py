"""
MCP (Model Context Protocol) Client Package for AI API Middleware

This package provides MCP client functionality to connect the middleware
to MCP servers, enabling access to external tools and data sources.

Components:
- client: Main MCP client class
- connection: Connection and session management
- tools: Tool discovery and invocation
- translator: Request/response translation layer
- orchestrator: Response merging and orchestration
"""

from .client import MCPClient
from .connection import MCPConnectionManager, MCPConnectionPool
from .tools import MCPToolManager, MCPToolInvoker
from .translator import MCPIntentDetector, MCPRequestTranslator
from .orchestrator import MCPResponseOrchestrator

__all__ = [
    'MCPClient',
    'MCPConnectionManager',
    'MCPConnectionPool',
    'MCPToolManager',
    'MCPToolInvoker',
    'MCPIntentDetector',
    'MCPRequestTranslator',
    'MCPResponseOrchestrator'
]

__version__ = "1.0.0"