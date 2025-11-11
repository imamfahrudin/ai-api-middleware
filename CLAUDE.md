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
- **proxy.py**: Central proxy logic with request transformation, provider detection, and failover handling
- **api_routes.py**: Admin API endpoints for key management and monitoring
- **auth.py**: Session-based authentication using MIDDLEWARE_PASSWORD
- **logging_utils.py**: In-memory live logging for dashboard

### Key Architecture Patterns

**Blueprint-based Structure**: The app uses Flask blueprints for modular route organization:
- `auth_bp`: Authentication endpoints (`/middleware/login`, `/middleware/logout`)
- `api_bp`: Admin API endpoints (`/middleware/api/*`)
- `proxy_bp`: Proxy endpoints for AI services (`/v1/*`, `/v1beta/*`)

**Thread-safe Database Operations**: KeyManager uses threading.Lock() for all database operations to handle concurrent requests safely.

**Smart Key Rotation**: Keys are rotated based on `last_rotated_at` timestamp to ensure even usage distribution. Failed keys are automatically marked as `Resting` (rate limits) or `Disabled` (auth errors).

**Provider Format Detection**: The proxy inspects request paths and bodies to determine the target API format (Gemini vs OpenAI-style) and transforms headers accordingly.

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