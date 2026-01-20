# flask application entry point
from flask import Flask
from backend.routes import register_routes

# Create Flask app
app = Flask(__name__, 
            template_folder='frontend/templates',
            static_folder='frontend/static')

# Set secret key for session management (needed for flash messages)
app.config['SECRET_KEY'] = 'dev-secret-key-change-in-production'

# Configure upload limits
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max request size

# Register routes
register_routes(app)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)