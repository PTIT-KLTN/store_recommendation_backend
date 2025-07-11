from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_bcrypt import Bcrypt
from config import Config
import os
from dotenv import load_dotenv

load_dotenv()

RADMIN_IP = os.getenv('RADMIN_IP')
RADMIN_NETWORK_NAME = os.getenv('RADMIN_NETWORK_NAME')
FLASK_PORT = os.getenv('FLASK_PORT')

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Enhanced CORS for Radmin VPN
    CORS(app, 
         origins=['*'],
         methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
         allow_headers=['Content-Type', 'Authorization'],
         supports_credentials=True)
    
    jwt = JWTManager(app)
    bcrypt = Bcrypt(app)
    
    # Health check endpoint
    @app.route('/health', methods=['GET'])
    def health_check():
        return {'status': 'healthy', 'radmin_ip': RADMIN_IP, 'network': RADMIN_NETWORK_NAME}
    
    # Register blueprints
    # from routes.auth_routes import auth_bp
    # from routes.public_routes import public_bp
    # from routes.user_routes import user_bp
    # from routes.basket_routes import basket_bp
    # from routes.ai_routes import ai_bp
    # from routes.admin_routes import admin_bp
    
    # app.register_blueprint(auth_bp, url_prefix='/api/v1/auth')
    # app.register_blueprint(public_bp, url_prefix='/api/v1/public')
    # app.register_blueprint(user_bp, url_prefix='/api/v1/user')
    # app.register_blueprint(basket_bp, url_prefix='/api/v1/basket')
    # app.register_blueprint(ai_bp, url_prefix='/api/v1/ai')
    # app.register_blueprint(admin_bp, url_prefix='/api/v1/admin')
    
    @app.route('/api/v1/test', methods=['GET'])
    def api_test():
        return {
            'message': 'API test successful',
            'network': RADMIN_NETWORK_NAME,
            'server_ip': RADMIN_IP
        }
    
    return app

if __name__ == '__main__':
    app = create_app()
    
    print(f"🚀 Flask API running on Radmin network: {RADMIN_NETWORK_NAME}")
    print(f"🌐 Access URL: http://{RADMIN_IP}:{FLASK_PORT}")
    print(f"📋 Test endpoint: http://{RADMIN_IP}:{FLASK_PORT}/api/v1/test")
    
    app.run(debug=True, host='0.0.0.0', port=FLASK_PORT)