# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI API Middleware is a Flask-based web application that provides a centralized proxy for AI API requests with built-in authentication, monitoring, and key management. It serves as a middleware layer between client applications and various AI services (primarily Google's Gemini API).

## Development Commands

### Running the Application
```bash
# Standard Python execution
python main.py

# With virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

### Docker Commands
```bash
# Build and run with Docker Compose
docker-compose up -d

# Stop the service
docker-compose down
```

### Dependencies
```bash
# Install required packages
pip install -r requirements.txt

# Core dependencies:
# - Flask: Web framework
# - requests: HTTP client for proxy requests
# - python-dotenv: Environment variable management
# - flasgger: Swagger/OpenAPI documentation
```

## Architecture

### Core Components

**main.py**: Application entry point that initializes Flask app, registers blueprints, and configures Swagger documentation.

**app/**: Main application package containing:
- **config.py**: Configuration management (SECRET_KEY, MIDDLEWARE_PASSWORD, DB_PATH)
- **database.py**: KeyManager class handles API key rotation, statistics tracking, and SQLite database operations
- **proxy.py**: Central proxy logic with request transformation, provider detection, failover handling, connection pooling, and streaming support
- **api_routes.py**: Admin API endpoints for key management and monitoring
- **auth.py**: Session-based authentication using MIDDLEWARE_PASSWORD
- **logging_utils.py**: In-memory live logging for dashboard
- **templates/**: Jinja2 templates for the web interface
  - **dashboard.html**: Main API key management dashboard
  - **login.html**: Authentication interface
  - **settings.html**: Performance and application settings management

### Key Architecture Patterns

**Blueprint-based Structure**: The app uses Flask blueprints for modular route organization:
- `auth_bp`: Authentication endpoints (`/middleware/login`, `/middleware/logout`)
- `api_bp`: Admin API endpoints (`/middleware/api/*`)
- `proxy_bp`: Proxy endpoints for AI services (`/v1/*`, `/v1beta/*`)

**Thread-safe Database Operations**: KeyManager uses threading.Lock() for all database operations to handle concurrent requests safely.

**Smart Key Rotation**: Keys are rotated based on `last_rotated_at` timestamp to ensure even usage distribution. Failed keys are automatically marked as `Resting` (rate limits) or `Disabled` (auth errors).

**Provider Format Detection**: The proxy inspects request paths and bodies to determine the target API format (Gemini vs OpenAI-style) and transforms headers accordingly.

**Connection Pooling & Performance**: HTTP requests use connection pooling with configurable retry strategies (total=3, backoff_factor=0.1) for better reliability and performance under load.

**Streaming Support**: The proxy supports streaming responses for real-time AI generation with proper backpressure handling and response caching.

**Response Caching**: Model discovery responses are cached for 5 minutes (configurable) to reduce API calls and improve response times.

### Database Schema

SQLite database at `data/keys.db` with tables:
- **keys**: Stores API keys with name, value, status, and metadata
- **daily_stats**: Aggregated usage statistics per key per day

Database migrations are handled manually in `KeyManager._initialize_db()` using safe column addition patterns.

## Important Runtime Behaviors

### Authentication Flow
- Session-based auth with `MIDDLEWARE_PASSWORD` from environment
- When `MIDDLEWARE_PASSWORD` is unset, authentication is bypassed (useful for local testing)
- Sessions use temporary SECRET_KEY generated at runtime (sessions don't persist across restarts)

### Proxy Request Processing
1. Request format detection (Gemini vs OpenAI-style)
2. API key selection using KeyManager.get_next_key()
3. Header transformation (Authorization: Bearer for OpenAI, x-goog-api-key for Gemini)
4. Request forwarding with failover logic
5. Response streaming back to client
6. Statistics logging and key status updates

### Key Lifecycle Management
- **Healthy**: Available for requests
- **Resting**: Temporarily disabled (rate limits, heals after timeout)
- **Disabled**: Permanently disabled (auth errors, manual intervention required)

## Testing & Development

### Access Points
- **Dashboard**: `http://localhost:5000/middleware/` (requires login)
- **Settings**: `http://localhost:5000/middleware/settings` (performance configuration)
- **API Docs**: `http://localhost:5000/middleware/swagger/` (interactive Swagger UI)
- **Login**: `http://localhost:5000/middleware/login`

### Example Proxy Request
```bash
curl -X POST http://localhost:5000/v1/models/gemini-pro:generateContent \
  -H "Content-Type: application/json" \
  -d '{
    "contents": [{
      "parts": [{"text": "Hello, how are you?"}]
    }]
  }'
```

### Environment Variables
Create `.env` file:
```
MIDDLEWARE_PASSWORD=your_secure_password
PORT=5000
FLASK_ENV=production
```

## Development Guidelines

### When Adding New API Providers
1. Add route patterns in `app/proxy.py`
2. Update provider format detection logic
3. Add proper Swagger documentation
4. Update header transformation logic

### Database Schema Changes
1. Use `PRAGMA table_info()` to check existing columns
2. Add new columns with ALTER TABLE statements
3. Provide default values for backwards compatibility
4. Update KeyManager methods accordingly

### Code Conventions
- Follow blueprint-based route registration
- Use session authentication via `@login_required` decorator
- All database operations must be thread-safe
- Add comprehensive Swagger documentation for new endpoints
- Use conventional commit messages (feat:, fix:, docs:, etc.)

### Testing Notes
- Use Swagger UI at `/middleware/swagger/` to test admin APIs
- Proxy endpoints can be tested directly with curl/requests
- Database is automatically created on first run at `data/keys.db`
- Live logs are available via `GET /middleware/api/logs` endpoint
- Settings page allows real-time performance tuning without restart
- Connection pool supports up to 100 concurrent connections with 20 base connections

### Performance Features
- **Retry Logic**: Configurable retry attempts (increased from 3 to 7 for better reliability)
- **Connection Pooling**: 20 base connections, 100 max connections with HTTP keep-alive
- **Response Caching**: 5-minute cache for model discovery endpoints
- **Streaming**: Real-time response streaming for generative AI endpoints
- **Backpressure Handling**: Proper flow control for streaming responses

## MCP (Model Context Protocol) Implementation

### Overview
The MCP implementation adds Model Context Protocol support to the AI API Middleware, enabling seamless integration with Claude Desktop and other MCP-compatible applications. This implementation transforms the middleware into a full-featured MCP server that can expose tools and resources to AI assistants.

### What is MCP?
Model Context Protocol (MCP) is an open protocol that standardizes how AI applications connect to data sources and tools. It provides:
- **Secure Communication**: Standardized request/response patterns between AI assistants and external tools
- **Tool Discovery**: Dynamic registration and discovery of available tools and resources
- **Resource Management**: Unified access to files, databases, APIs, and other resources
- **Session Management**: Persistent connections with proper authentication and authorization

### Current Implementation Status

#### ✅ What's Working
- **MCP Client Discovery**: Automatic detection and connection to running MCP servers
- **Tool Registration**: Dynamic registration of MCP tools as middleware endpoints
- **Basic Proxy Integration**: Forwarding of tool requests to MCP servers
- **Database Schema**: MCP server and tool storage implemented
- **UI Foundation**: Basic MCP management interface added to dashboard
- **API Endpoints**: Core CRUD operations for MCP server management

#### 🚧 In Progress
- **Tool Execution**: Enhanced error handling and response formatting
- **Resource Management**: File and resource access through MCP protocol
- **Real-time Updates**: Live status updates for MCP server connections
- **Authentication**: Secure token-based authentication for MCP connections

#### ❌ Not Yet Implemented
- **Advanced Tool Features**: Streaming responses, progress indicators
- **Resource Caching**: Intelligent caching of MCP resource responses
- **Tool Composition**: Combining multiple MCP tools in workflows
- **Monitoring**: Comprehensive logging and performance metrics for MCP operations

### Architecture Overview

#### MCP Integration Layer
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Claude Desktop│◄──►│  AI API Middleware│◄──►│   MCP Servers   │
│   (MCP Client)  │    │   (MCP Proxy)    │    │  (Tool Providers)│
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │  AI API Proxy   │
                       │  (OpenAI/Gemini)│
                       └─────────────────┘
```

#### Core Components
- **MCP Client**: Handles connection management and protocol communication with MCP servers
- **Tool Registry**: Dynamic registration and mapping of MCP tools to HTTP endpoints
- **Request Router**: Intelligent routing between MCP tools and AI API endpoints
- **Resource Manager**: Unified access to files, databases, and external resources
- **Session Handler**: Persistent connection management with proper cleanup

### Database Schema Changes

#### New Tables Added
```sql
-- MCP server configurations
CREATE TABLE mcp_servers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    transport_type TEXT NOT NULL, -- 'stdio' or 'sse'
    command TEXT,                 -- Command for stdio transport
    args TEXT,                    -- JSON array of arguments
    env TEXT,                     -- JSON object of environment variables
    url TEXT,                     -- URL for SSE transport
    headers TEXT,                 -- JSON object of headers for SSE
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Registered MCP tools
CREATE TABLE mcp_tools (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    server_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    input_schema TEXT,            -- JSON schema for tool inputs
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (server_id) REFERENCES mcp_servers (id) ON DELETE CASCADE
);
```

### API Endpoints Created

#### MCP Server Management
- `GET /middleware/api/mcp/servers` - List all MCP servers
- `POST /middleware/api/mcp/servers` - Create new MCP server
- `PUT /middleware/api/mcp/servers/{id}` - Update MCP server configuration
- `DELETE /middleware/api/mcp/servers/{id}` - Delete MCP server
- `POST /middleware/api/mcp/servers/{id}/connect` - Connect to MCP server
- `POST /middleware/api/mcp/servers/{id}/disconnect` - Disconnect from MCP server

#### Tool Management
- `GET /middleware/api/mcp/tools` - List all registered MCP tools
- `GET /middleware/api/mcp/tools/{id}` - Get specific tool details
- `POST /middleware/api/mcp/tools/{id}/execute` - Execute MCP tool
- `GET /middleware/api/mcp/servers/{id}/tools` - List tools for specific server

#### Status and Monitoring
- `GET /middleware/api/mcp/status` - Get overall MCP system status
- `GET /middleware/api/mcp/servers/{id}/status` - Get server connection status

### UI Components Added

#### Dashboard Integration
- **MCP Servers Section**: New panel in main dashboard showing active MCP servers
- **Tool Browser**: Interface to browse and inspect available MCP tools
- **Connection Status**: Real-time status indicators for MCP server connections
- **Quick Actions**: Connect/disconnect buttons and tool testing interface

#### MCP Management Pages
- **MCP Servers Page**: `/middleware/mcp/servers` - Full CRUD interface for server management
- **Tool Explorer**: `/middleware/mcp/tools` - Browse and test MCP tools
- **Connection Logs**: `/middleware/mcp/logs` - View MCP connection and execution logs

### Known Issues and Limitations

#### Current Limitations
1. **Connection Reliability**: MCP server connections may timeout after long periods of inactivity
2. **Error Handling**: Limited error recovery for failed tool executions
3. **Tool Discovery**: Some MCP servers may not properly advertise all available tools
4. **Resource Access**: File system access through MCP is currently restricted for security
5. **Performance**: No caching mechanism for MCP tool responses
6. **Authentication**: Limited support for token-based authentication schemes

#### Security Considerations
- MCP servers run with the same permissions as the middleware application
- File system access should be carefully configured and restricted
- Tool execution timeouts are in place but may need adjustment based on use case
- Input validation is basic and should be enhanced for production use

### Configuration Examples

#### Stdio Transport MCP Server
```json
{
    "name": "filesystem-server",
    "transport_type": "stdio",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp/mcp-files"],
    "env": {
        "NODE_ENV": "production"
    }
}
```

#### SSE Transport MCP Server
```json
{
    "name": "weather-server",
    "transport_type": "sse",
    "url": "http://localhost:8080/sse",
    "headers": {
        "Authorization": "Bearer your-api-token"
    }
}
```

### Testing MCP Integration

#### Example Tool Execution
```bash
# List available MCP tools
curl -H "Authorization: Bearer YOUR_SESSION_TOKEN" \
     http://localhost:5000/middleware/api/mcp/tools

# Execute a filesystem tool
curl -X POST \
     -H "Authorization: Bearer YOUR_SESSION_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"path": "/tmp/test.txt"}' \
     http://localhost:5000/middleware/api/mcp/tools/1/execute
```

## MCP Implementation Todo List

### Phase 1: Foundation Completion (Immediate)
- [ ] **Enhanced Error Handling**: Implement comprehensive error recovery for MCP connections
- [ ] **Tool Input Validation**: Add JSON schema validation for all MCP tool inputs
- [ ] **Connection Pooling**: Implement connection pooling for multiple MCP server instances
- [ ] **Session Persistence**: Maintain MCP connections across application restarts
- [ ] **Unit Tests**: Add comprehensive test coverage for MCP client and tool execution

### Phase 2: Feature Enhancement (Next Sprint)
- [ ] **Resource Caching**: Implement intelligent caching for MCP resource responses
- [ ] **Streaming Support**: Add support for streaming responses from MCP tools
- [ ] **Tool Composition**: Enable chaining multiple MCP tools in workflows
- [ ] **Advanced Authentication**: Support OAuth, API keys, and custom auth schemes
- [ ] **Performance Monitoring**: Add metrics and logging for MCP operation performance

### Phase 3: Advanced Features (Future)
- [ ] **Tool Versioning**: Support multiple versions of the same tool
- [ ] **Dynamic Tool Loading**: Hot-reload MCP tools without server restart
- [ ] **Multi-tenant Support**: Isolate MCP tools by user or organization
- [ ] **Tool Marketplace**: Pre-configured MCP server templates and community tools
- [ ] **GraphQL Integration**: Expose MCP tools through GraphQL interface

### Phase 4: Production Readiness
- [ ] **Security Audit**: Comprehensive security review of MCP implementation
- [ ] **Load Testing**: Performance testing under high concurrent load
- [ ] **Documentation**: Complete API documentation and user guides
- [ ] **Monitoring Integration**: Prometheus metrics and health check endpoints
- [ ] **Backup/Restore**: MCP configuration backup and disaster recovery

### Bug Fixes and Improvements
- [ ] Fix connection timeout issues with long-running MCP servers
- [ ] Improve tool discovery to handle non-compliant MCP implementations
- [ ] Add retry logic for failed tool executions
- [ ] Optimize database queries for MCP server and tool listings
- [ ] Enhance UI responsiveness for large numbers of MCP tools
- [ ] Add configuration validation before saving MCP server settings

### Research and Investigation
- [ ] Evaluate MCP server ecosystem and popular implementations
- [ ] Research best practices for MCP tool security and isolation
- [ ] Investigate integration patterns with existing AI workflows
- [ ] Study performance characteristics of different transport mechanisms
- [ ] Analyze compatibility with various MCP client implementations