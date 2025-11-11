import os
import logging
from flask import Flask, render_template
from dotenv import load_dotenv
from flasgger import Swagger

# Load environment variables from .env file
load_dotenv()

# --- App Imports ---
from app.config import SECRET_KEY
from app.auth import auth_bp, login_required
from app.api_routes import api_bp
from app.proxy import proxy_bp
from app.mcp_integration import initialize_mcp_integration
from app.mcp_sessions import initialize_mcp_sessions
from app.database import KeyManager

# --- Logging Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Flask App Initialization ---
app = Flask(
    __name__, 
    template_folder=os.path.join(os.path.dirname(__file__), 'app', 'templates'),
    static_folder=os.path.join(os.path.dirname(__file__), 'app', 'static'),
    static_url_path='/middleware/static'
)
app.secret_key = SECRET_KEY

# --- Swagger Configuration ---
swagger_config = {
    "headers": [],
    "specs": [
        {
            "endpoint": 'apispec',
            "route": '/middleware/apispec.json',
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/middleware/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/middleware/swagger/"
}

swagger_template = {
    "swagger": "2.0",
    "info": {
        "title": "AI API Middleware",
        "description": "API documentation for AI API Middleware - Proxy and Management System. **Note:** You must be logged in to test the APIs. Please login at `/middleware/login` first.",
        "version": "1.0.0"
    },
    "basePath": "/",
    "schemes": ["http", "https"],
    "securityDefinitions": {
        "SessionAuth": {
            "type": "apiKey",
            "name": "session",
            "in": "cookie",
            "description": "Session-based authentication. Login at /middleware/login to get a session cookie."
        }
    },
    "security": [
        {
            "SessionAuth": []
        }
    ]
}

swagger = Swagger(app, config=swagger_config, template=swagger_template)

# --- Register Blueprints ---
app.register_blueprint(auth_bp)
app.register_blueprint(api_bp)
app.register_blueprint(proxy_bp)

# --- Initialize MCP Integration ---
try:
    key_manager = KeyManager()
    initialize_mcp_integration(key_manager)
    initialize_mcp_sessions(key_manager)
    logging.info("MCP integration and sessions initialized successfully")
except Exception as e:
    logging.error(f"Failed to initialize MCP integration: {str(e)}")

# --- Dashboard Route ---
@app.route('/middleware/')
@login_required
def dashboard():
    return render_template('dashboard.html')

# --- Settings Route ---
@app.route('/middleware/settings')
@login_required
def settings():
    return render_template('settings.html')

# --- Main Execution ---
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

