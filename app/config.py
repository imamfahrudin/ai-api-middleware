import os

# --- Flask App Configuration ---
SECRET_KEY = os.urandom(24) # Needed for session management
MIDDLEWARE_PASSWORD = os.environ.get('MIDDLEWARE_PASSWORD')

# --- Database Configuration ---
DB_PATH = 'data/keys.db'
