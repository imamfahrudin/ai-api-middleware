# AI API Middleware 🚀

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![Flask](https://img.shields.io/badge/flask-latest-green.svg)
![Docker](https://img.shields.io/badge/docker-ready-brightgreen.svg)
![Maintenance](https://img.shields.io/badge/maintained-yes-green.svg)

A powerful middleware solution for managing and proxying AI API requests with built-in authentication, monitoring, and key management. Perfect for developers who need to centralize, monitor, and control access to multiple AI API keys with detailed logging and analytics.

## 📋 Table of Contents

- [Features](#-features)
- [Prerequisites](#-prerequisites)
- [Installation](#-installation)
- [Usage](#-usage)
- [Configuration](#-configuration)
- [API Documentation](#-api-documentation)
- [Contributing](#-contributing)
- [Support](#-support)

## ✨ Features

- **🔐 Secure Authentication**: Built-in login system with session management to protect your API endpoints
- **🔑 Advanced API Key Management**: Create, update, delete, and monitor multiple API keys with bulk operations and import/export functionality
- **📊 Real-time Monitoring**: Track API usage with live logs and detailed KPI metrics (requests, success/failure rates, latency, token usage)
- **🔄 Smart Proxy**: Seamlessly proxy requests to various AI services (Gemini, OpenAI, and more) with intelligent failover
- **📈 Analytics Dashboard**: Beautiful web interface to visualize API usage and performance metrics with detailed charts
- **⚙️ Performance Settings**: Real-time performance tuning without application restart including timeout configurations
- **📝 Comprehensive Logging**: Track all API requests with timestamps, status codes, response times, and error details
- **🚀 High Performance**: Connection pooling, response caching, and streaming support for optimal speed
- **🔄 Advanced Retry Logic**: Configurable retry attempts (up to 7) with exponential backoff and streaming retry
- **🐳 Docker Support**: Easy deployment with Docker and Docker Compose
- **📚 Auto-generated API Docs**: Interactive Swagger/OpenAPI documentation for all endpoints
- **⚡ Lightweight**: Built with Flask for fast performance and minimal resource usage
- **📦 Bulk Operations**: Import/export API keys in bulk with status management and validation
- **🔧 Enhanced Timeout Configuration**: Granular control over connection, read, and streaming timeouts

## 📦 Prerequisites

Before you begin, ensure you have the following installed:

- **Python 3.8+** - [Download Python](https://www.python.org/downloads/)
- **pip** - Python package installer (comes with Python)
- **Docker & Docker Compose** (optional, for containerized deployment) - [Get Docker](https://www.docker.com/get-started)
- **Git** - [Install Git](https://git-scm.com/downloads)

## 🚀 Installation

### Option 1: Standard Installation

1. **Clone the repository**
```bash
git clone https://github.com/imamfahrudin/ai-api-middleware.git
cd ai-api-middleware
```

2. **Create a virtual environment** (recommended)
```bash
python -m venv venv

# On Windows
venv\Scripts\activate

# On macOS/Linux
source venv/bin/activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Set up environment variables**
```bash
# Copy the example environment file
cp .env.example .env

# Edit .env and set your password
# MIDDLEWARE_PASSWORD=your_secure_password_here
```

5. **Run the application**
```bash
python main.py
```

The application will be available at `http://localhost:5000`

### Option 2: Docker Installation

1. **Clone the repository**
```bash
git clone https://github.com/imamfahrudin/ai-api-middleware.git
cd ai-api-middleware
```

2. **Create your .env file**
```bash
# Create .env file with your configuration
echo "MIDDLEWARE_PASSWORD=your_secure_password_here" > .env
```

3. **Build and run with Docker Compose**
```bash
docker-compose up -d
```

The application will be available at `http://localhost:5000`

## 🎮 Usage

### Accessing the Dashboard

1. Navigate to `http://localhost:5000/middleware/login`
2. Enter your password (set in `.env` file)
3. Access the dashboard to manage your API keys

### Managing API Keys

From the dashboard, you can:
- **Add new API keys**: Click "Add New Key" and provide a name, key value, and optional notes
- **View KPIs**: Monitor total requests, success rates, failure rates, latency, and token usage for each key
- **Edit keys**: Update key names, values, status, or notes
- **Delete keys**: Remove keys that are no longer needed
- **View live logs**: See real-time API request logs with detailed information
- **Bulk operations**: Select multiple keys to update status or delete them in bulk
- **Import/Export keys**: Backup your keys or import them from another instance
- **Advanced metrics**: View detailed analytics with charts for requests, models, errors, and latency

### Performance Settings

Navigate to `http://localhost:5000/middleware/settings` to configure:
- **Connection Pool Size**: Adjust base and maximum connections (default: 20 base, 100 max)
- **Retry Attempts**: Configure retry logic for failed requests (default: 7 attempts)
- **Cache Timeout**: Set response caching duration for model discovery (default: 5 minutes)
- **Timeout Configuration**: Fine-tune connection, read, and streaming timeouts
- **Streaming**: Enable/disable response streaming for real-time generation
- **Max Stream Retries**: Configure retry attempts for streaming chunks (default: 2)

All settings are applied in real-time without requiring application restart.

### Using the Proxy

#### Example 1: Proxying Gemini API Requests

```bash
# Make a request through the middleware
curl -X POST http://localhost:5000/v1/models/gemini-pro:generateContent \
  -H "Content-Type: application/json" \
  -d '{
    "contents": [{
      "parts": [{
        "text": "Hello, how are you?"
      }]
    }]
  }'
```

#### Example 2: Streaming Responses with Enhanced Retry

```python
import requests

# Enable streaming for real-time responses with automatic retry
response = requests.post(
    "http://localhost:5000/v1/models/gemini-pro:streamGenerateContent",
    json={
      "contents": [{
        "parts": [{"text": "Write a story about AI"}]
      }]
    },
    stream=True
)

# Process the response as it streams in with automatic retry on failures
for line in response.iter_lines():
    if line:
        print(line.decode('utf-8'))
```

#### Example 3: Counting Tokens

```python
import requests

# Count tokens before making a request
response = requests.post(
    "http://localhost:5000/v1/models/gemini-pro:countTokens",
    json={
      "contents": [{
        "parts": [{"text": "Explain quantum computing"}]
      }]
    }
)

print(response.json())
```

#### Example 4: Using with Your Application

```python
import requests

# Your application makes requests through the middleware
response = requests.post(
    "http://localhost:5000/v1/models/gemini-pro:generateContent",
    json={
      "contents": [{
        "parts": [{"text": "Explain quantum computing"}]
      }]
    }
)

print(response.json())
```

> **Note**: The middleware automatically selects and rotates available API keys, handles errors with intelligent retry logic, and logs all requests for monitoring. Connection pooling ensures optimal performance under load. Enhanced streaming includes chunk-level retry with graceful degradation.

### Bulk Operations

#### Importing and Exporting API Keys

The middleware supports bulk operations to easily manage multiple API keys:

**Exporting Keys:**
1. Navigate to `http://localhost:5000/middleware/keys`
2. Click the "Import / Export" button
3. Click "Copy to Clipboard" to export all keys as JSON
4. Store the exported JSON securely as a backup

**Importing Keys:**
1. Click the "Import / Export" button in the keys management interface
2. Paste your JSON backup in the import textarea
3. Click "Import from Text" to import all keys
4. Existing keys (based on key value) will be automatically skipped

**Export Format:**
```json
[
  {
    "name": "Production Key",
    "key_value": "AIzaSy...",
    "note": "Main production API key"
  },
  {
    "name": "Development Key",
    "key_value": "AIzaSy...",
    "note": "Used for testing and development"
  }
]
```

#### Bulk Actions

Perform bulk operations on multiple keys at once:

1. Select multiple keys using the checkboxes in the keys table
2. Choose from the bulk actions dropdown:
   - **Set Healthy**: Mark selected keys as healthy and available for use
   - **Set Disabled**: Disable selected keys temporarily
   - **Delete Selected**: Permanently remove selected keys
3. Click "Apply" to execute the bulk action

> **Note**: Bulk actions are irreversible for delete operations. Always export your keys before performing bulk deletions.

### Viewing API Documentation

Navigate to `http://localhost:5000/middleware/swagger/` to access the interactive Swagger UI with full API documentation.

### Advanced Timeout Configuration

The middleware provides comprehensive timeout configuration for different scenarios:

#### Timeout Types

- **Connection Timeout**: Time to establish the initial TCP connection (default: 10 seconds)
- **Read Timeout**: Time to wait for response headers/initial data after connection (default: 60 seconds)
- **Streaming Timeout**: Time to wait for each chunk during streaming operations (default: 120 seconds)
- **Request Timeout**: Legacy timeout setting (still supported for backward compatibility)

#### Configuration

All timeout settings can be configured via the settings interface:

1. Navigate to `http://localhost:5000/middleware/settings`
2. Adjust timeout values based on your needs:
   - **Connect Timeout**: 5-30 seconds (recommended: 10 seconds)
   - **Read Timeout**: 30-120 seconds (recommended: 60 seconds)
   - **Streaming Timeout**: 60-300 seconds (recommended: 120 seconds)
   - **Max Stream Retries**: 1-5 attempts (recommended: 2 attempts)

#### Timeout Behavior

- **Connection Timeouts**: Trigger automatic key failover and retry logic
- **Read Timeouts**: Trigger retry with exponential backoff
- **Streaming Timeouts**: Implement chunk-level retry with graceful degradation
- **Buffer Optimization**: Dynamic buffer sizing based on request size and content type

#### Streaming with Retry Logic

The enhanced streaming includes automatic retry mechanisms:

- **Max Retries**: Configurable attempts per failed chunk
- **Backoff Strategy**: Exponential backoff (1s, 2s, 4s...)
- **Graceful Degradation**: Attempts to provide partial response on complete failure
- **Resource Management**: Automatic connection cleanup and memory-efficient buffering

For detailed timeout configuration information, see the [Timeout Configuration Guide](TIMEOUT_CONFIGURATION.md).

## ⚙️ Configuration

Configuration is managed through environment variables. Create a `.env` file in the root directory:

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `MIDDLEWARE_PASSWORD` | Password to access the middleware dashboard | `null` | ✅ Yes |
| `PORT` | Port to run the application on | `5000` | ❌ No |
| `FLASK_ENV` | Flask environment (development/production) | `production` | ❌ No |

### Example .env file

```env
# Required: Set your secure password
MIDDLEWARE_PASSWORD=your_very_secure_password_123

# Optional: Custom port (defaults to 5000)
# PORT=8080

# Optional: Development mode
# FLASK_ENV=development
```

### Database

The middleware uses SQLite for data persistence. The database file is automatically created at `data/keys.db` on first run. This directory is mounted as a volume in Docker to ensure data persistence across container restarts.

### Performance Configuration

The middleware includes intelligent performance optimizations:

- **Connection Pooling**: 20 base connections, 100 max connections with HTTP keep-alive
- **Retry Logic**: Up to 7 retry attempts with exponential backoff for failed requests
- **Response Caching**: 5-minute cache for model discovery endpoints
- **Streaming Support**: Real-time response streaming for generative AI with chunk-level retry
- **Thread Safety**: All database operations use thread-safe locks
- **Dynamic Buffer Optimization**: Automatic buffer sizing based on request characteristics
- **Enhanced Timeout Management**: Granular control over connection, read, and streaming timeouts

These settings can be configured in real-time via the settings page without application restart.

## 📚 API Documentation

### Authentication Endpoints

- `POST /middleware/login` - Login to the dashboard
- `POST /middleware/logout` - Logout from the dashboard

### Key Management Endpoints

- `GET /middleware/api/keys` - Get all API keys with KPI data
- `GET /middleware/api/keys/<id>` - Get specific key details
- `GET /middleware/api/keys/<id>/stats` - Get detailed statistics for a specific key
- `POST /middleware/api/keys` - Create a new API key
- `POST /middleware/api/keys/bulk-action` - Perform bulk actions on multiple keys
- `PUT /middleware/api/keys/<id>` - Update an existing key
- `DELETE /middleware/api/keys/<id>` - Delete a key
- `GET /middleware/api/keys/export` - Export all API keys
- `POST /middleware/api/keys/import` - Import API keys in bulk

### Monitoring Endpoints

- `GET /middleware/api/logs` - Get live request logs
- `GET /middleware/api/global-stats` - Get global statistics across all keys
- `GET /middleware/dashboard` - Access the web dashboard
- `GET /middleware/settings` - Access performance settings page
- `GET /middleware/keys` - Access the key management interface

### Proxy Endpoints

- `POST /v1/models/<model>:generateContent` - Gemini API proxy
- `POST /v1beta/models/<model>:generateContent` - Gemini Beta API proxy
- `POST /v1/models/<model>:streamGenerateContent` - Gemini streaming API proxy
- `POST /v1beta/models/<model>:streamGenerateContent` - Gemini Beta streaming API proxy
- `POST /v1/models/<model>:countTokens` - Gemini token counting API proxy
- `POST /v1beta/models/<model>:countTokens` - Gemini Beta token counting API proxy
- `GET /v1/models` - Model discovery (with 5-minute caching)
- `GET /v1beta/models` - Gemini Beta model discovery (with 5-minute caching)
- `POST /v1/chat/completions` - OpenAI-style API proxy
- `GET /<path>` - Generic proxy for any other API endpoints
- Additional proxy endpoints available - see Swagger docs

### Settings Endpoints

- `GET /middleware/api/settings` - Get current performance settings
- `GET /middleware/api/settings/<setting_key>` - Get a specific setting value
- `POST /middleware/api/settings` - Update performance settings
- `POST /middleware/api/settings/reset` - Reset settings to defaults

For detailed API documentation with request/response schemas, visit `/middleware/swagger/` when the application is running.

## 🤝 Contributing

We welcome contributions! Here's how you can help:

1. **Fork the repository**
2. **Create a new branch**: `git checkout -b feature/your-awesome-feature`
3. **Make your changes** and ensure code quality
4. **Commit your changes**: `git commit -m 'feat: add your awesome feature'`
5. **Push to the branch**: `git push origin feature/your-awesome-feature`
6. **Open a Pull Request**

### Development Guidelines

- Follow PEP 8 style guide for Python code
- Add comments for complex logic
- Update documentation for new features
- Test your changes thoroughly before submitting
- Use conventional commit messages:
  - `feat:` for new features
  - `fix:` for bug fixes
  - `docs:` for documentation changes
  - `refactor:` for code refactoring
  - `test:` for adding tests
  - `chore:` for maintenance tasks

## Acknowledgments

- Built with [Flask](https://flask.palletsprojects.com/) - The lightweight Python web framework
- API documentation powered by [Flasgger](https://github.com/flasgger/flasgger) (Swagger UI)
- Icons and design inspiration from modern web standards

## 💬 Support

If you have questions, run into issues, or want to request features:

- **GitHub Issues**: [Open an issue](https://github.com/imamfahrudin/ai-api-middleware/issues)
- **Discussions**: [Start a discussion](https://github.com/imamfahrudin/ai-api-middleware/discussions)
- **Project Lead**: [imamfahrudin](https://github.com/imamfahrudin)

---

<div align="center">
<sub>Made with ❤️ by <a href="https://github.com/imamfahrudin">Mukhammad Imam Fahrudin</a></sub>
</div>
