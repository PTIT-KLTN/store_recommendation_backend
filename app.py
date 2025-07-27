from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_bcrypt import Bcrypt
import os
from dotenv import load_dotenv
from datetime import timedelta

load_dotenv()

RADMIN_IP = os.getenv('RADMIN_IP')
RADMIN_NETWORK_NAME = os.getenv('RADMIN_NETWORK_NAME')
FLASK_PORT = os.getenv('FLASK_PORT')

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
    
    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=int(os.getenv('JWT_ACCESS_TOKEN_EXPIRES_HOURS', 24)))
    app.config['JWT_REFRESH_TOKEN_EXPIRES'] = timedelta(days=int(os.getenv('JWT_REFRESH_TOKEN_EXPIRES_DAYS', 90)))
    
    CORS(app, 
         origins=['http://localhost:3000', 'http://127.0.0.1:3000', f'http://{RADMIN_IP}:3000'],
         methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS', 'PATCH'],
         allow_headers=[
             'Content-Type', 
             'Authorization', 
             'Access-Control-Allow-Credentials',
             'Access-Control-Allow-Origin',
             'Access-Control-Allow-Headers',
             'Access-Control-Allow-Methods',
             'X-Requested-With',
             'Accept',
             'Origin'
         ],
         supports_credentials=True,
         send_wildcard=False,
         max_age=3600)
    
    jwt = JWTManager(app)
    bcrypt = Bcrypt(app)
    
    # Register blueprints
    from routes.auth_routes import auth_bp
    from routes.public_routes import public_bp
    from routes.user_routes import user_bp
    from routes.basket_routes import basket_bp
    # from routes.ai_routes import ai_bp
    from routes.calculate_routes import calculate_bp
    from routes.admin_routes import admin_bp
    from routes.store_routes import store_bp
    from routes.crawling_routes import crawling_bp
    
    app.register_blueprint(auth_bp, url_prefix='/api/v1/auth')
    app.register_blueprint(public_bp, url_prefix='/api/v1/public')
    app.register_blueprint(user_bp, url_prefix='/api/v1/user')
    app.register_blueprint(basket_bp, url_prefix='/api/v1/basket')
    # app.register_blueprint(ai_bp, url_prefix='/api/v1/ai')
    app.register_blueprint(calculate_bp, url_prefix='/api/v1/calculate')
    app.register_blueprint(admin_bp, url_prefix='/api/v1/admin')
    app.register_blueprint(store_bp, url_prefix='/api/v1/stores')
    app.register_blueprint(crawling_bp, url_prefix='/api/v1/crawling')

        
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
    # celery_app.start()
    print(f"Flask API running on Radmin network: {RADMIN_NETWORK_NAME}")
    print(f"Access URL: http://{RADMIN_IP}:{FLASK_PORT}")
    print(f"Test endpoint: http://{RADMIN_IP}:{FLASK_PORT}/api/v1/test")
    
    app.run(debug=True, host='0.0.0.0', port=FLASK_PORT, threaded=True, use_reloader=True)
