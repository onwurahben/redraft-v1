import os
import sys

# Fix ModuleNotFoundError when running directly from app/ dir
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Flask
from utils.logger import get_logger
from app.routes import register_routes
import logging

# Silence Supabase/httpx outgoing requests details
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)

# Filter out frequent polling logs from Werkzeug, but keep startup/error logs
class PollingFilter(logging.Filter):
    def filter(self, record):
        msg = record.getMessage()
        return not ("/api/stats" in msg or "/api/progress" in msg)

logging.getLogger('werkzeug').addFilter(PollingFilter())

logger = get_logger("Flask Entry")

app = Flask(__name__, template_folder='../templates', static_folder='../static')

# Register all routes from routes.py
register_routes(app)

if __name__ == '__main__':
    host = os.getenv("FLASK_HOST", "127.0.0.1")
    port = int(os.getenv("FLASK_PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "True").lower() == "true"
    
    print(f"Starting Flask Server on {host}:{port} (debug={debug})...")
    app.run(debug=debug, host=host, port=port)
