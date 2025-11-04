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
- **🔑 API Key Management**: Create, update, delete, and monitor multiple API keys from a centralized dashboard
- **📊 Real-time Monitoring**: Track API usage with live logs and detailed KPI metrics (requests, success/failure rates)
- **🔄 Smart Proxy**: Seamlessly proxy requests to various AI services (Gemini, OpenAI, and more)
- **📈 Analytics Dashboard**: Beautiful web interface to visualize API usage and performance metrics
- **📝 Comprehensive Logging**: Track all API requests with timestamps, status codes, and response times
- **🐳 Docker Support**: Easy deployment with Docker and Docker Compose
- **📚 Auto-generated API Docs**: Interactive Swagger/OpenAPI documentation for all endpoints
- **⚡ Lightweight**: Built with Flask for fast performance and minimal resource usage

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
- **Add new API keys**: Click "Add New Key" and provide a name and key value
- **View KPIs**: Monitor total requests, success rates, and failure rates for each key
- **Edit keys**: Update key names, values, or status
- **Delete keys**: Remove keys that are no longer needed
- **View live logs**: See real-time API request logs with detailed information

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

#### Example 2: Using with Your Application

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

> **Note**: The middleware automatically selects and rotates available API keys, handles errors, and logs all requests for monitoring.

### Viewing API Documentation

Navigate to `http://localhost:5000/middleware/swagger/` to access the interactive Swagger UI with full API documentation.

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

## 📚 API Documentation

### Authentication Endpoints

- `POST /middleware/login` - Login to the dashboard
- `POST /middleware/logout` - Logout from the dashboard

### Key Management Endpoints

- `GET /middleware/api/keys` - Get all API keys with KPI data
- `GET /middleware/api/keys/<id>` - Get specific key details
- `POST /middleware/api/keys` - Create a new API key
- `PUT /middleware/api/keys/<id>` - Update an existing key
- `DELETE /middleware/api/keys/<id>` - Delete a key

### Monitoring Endpoints

- `GET /middleware/api/logs` - Get live request logs
- `GET /middleware/dashboard` - Access the web dashboard

### Proxy Endpoints

- `POST /v1/models/<model>:generateContent` - Gemini API proxy
- `POST /v1beta/models/<model>:generateContent` - Gemini Beta API proxy
- Additional proxy endpoints available - see Swagger docs

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

##  Acknowledgments

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
