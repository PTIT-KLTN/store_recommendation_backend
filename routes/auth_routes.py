from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from flask_bcrypt import generate_password_hash, check_password_hash
from datetime import datetime
from services.google_oauth_service import google_oauth_service
from services.auth_service import process_user, create_user_profile
from validators.auth_validators import validate_email, validate_password
from utils.token_utils import create_user_tokens
from database.mongodb import MongoDBConnection
from services.forgot_password_service import request_password_reset_service, reset_password_service, verify_reset_token_service

auth_bp = Blueprint('auth', __name__)
db = MongoDBConnection.get_primary_db()

@auth_bp.route('/register', methods=['POST'])
def register():
    """Register new user"""
    try:
        data = request.get_json()
        
        if not data or not all(k in data for k in ('email', 'password', 'fullname')):
            return jsonify({'message': 'Email, mật khẩu và họ tên là bắt buộc'}), 400
        
        if not validate_email(data['email']):
            return jsonify({'message': 'Định dạng email không hợp lệ'}), 400
        
        result = process_user(data, auth_provider='local')
        return jsonify(result), 201
        
    except Exception as e:
        return jsonify({'message': str(e)}), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    """User login"""
    try:
        data = request.get_json()
        
        if not data or not all(k in data for k in ('email', 'password')):
            return jsonify({'message': 'Email và mật khẩu là bắt buộc'}), 400
                
        user_data = db.users.find_one({'email': data['email']})
        if not user_data:
            return jsonify({'message': 'Email hoặc mật khẩu không chính xác'}), 401
        
        if not check_password_hash(user_data['password'], data['password']):
            return jsonify({'message': 'Email hoặc mật khẩu không chính xác'}), 401
        
        if not user_data.get('is_enabled', True):
            return jsonify({'message': 'Tài khoản đã bị vô hiệu hóa'}), 401

        access_token, refresh_token = create_user_tokens(data['email'], 'local')
        user_profile = create_user_profile(user_data, 'local')
        
        return jsonify({
            'access_token': access_token,
            'refresh_token': refresh_token,
            'user': user_profile,
            'message': 'Đăng nhập thành công'
        }), 200
        
    except Exception as e:
        return jsonify({'message': f'Đăng nhập thất bại: {str(e)}'}), 500

@auth_bp.route('/refresh', methods=['POST'])
def refresh():
    """Refresh access token using refresh token"""
    try:
        data = request.get_json()
    
        if not data or 'refresh_token' not in data:
            return jsonify({'message': 'Refresh token là bắt buộc'}), 400
                
        refresh_token_doc = db.refresh_tokens.find_one({
            'refresh_token': data['refresh_token']
        })
        
        if not refresh_token_doc:
            return jsonify({'message': 'Refresh token không hợp lệ'}), 401
        
        if refresh_token_doc['expiration_time'] < datetime.utcnow():
            db.refresh_tokens.delete_one({'_id': refresh_token_doc['_id']})
            return jsonify({'message': 'Refresh token đã hết hạn'}), 401
        
        user_email = refresh_token_doc['user_email']
        
        user_doc = db.users.find_one({'email': user_email})
        if not user_doc or not user_doc.get('is_enabled', True):
            return jsonify({'message': 'User not found or disabled'}), 401
        
        access_token = create_access_token(identity=user_email)
        
        return jsonify({
            'access_token': access_token,
            'refresh_token': data['refresh_token'],
            'message': 'Làm mới token thành công'
        }), 200
        
    except Exception as e:
        return jsonify({'message': f'Làm mới token thất bại: {str(e)}'}), 500

@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """User logout"""
    try:
        current_user = get_jwt_identity()        
        db.refresh_tokens.delete_many({'user_email': current_user})
        return jsonify({'message': 'Đăng xuất thành công'}), 200
    except Exception as e:
        return jsonify({'message': f'Đăng xuất thất bại: {str(e)}'}), 500

@auth_bp.route('/google/callback-frontend', methods=['POST'])
def google_callback_frontend():
    """Handle Google OAuth callback from frontend"""
    try:
        data = request.get_json()
        
        if not data or 'code' not in data:
            return jsonify({
                'message': 'Mã xác thực là bắt buộc',
                'error': 'MISSING_AUTH_CODE'
            }), 400
        
        authorization_code = data['code']
        
        if not google_oauth_service.client_secret:
            return jsonify({
                'message': 'Google Client Secret chưa được cấu hình', 
                'error': 'MISSING_CLIENT_SECRET'
            }), 500
        
        token_data = google_oauth_service.exchange_code_for_token(authorization_code)
        access_token = token_data.get('access_token')
        
        if not access_token:
            raise Exception("No access token received from Google")
        
        google_user_info = google_oauth_service.get_user_info(access_token)
        
        user_data = {
            'email': google_user_info.get('email'),
            'fullname': google_user_info.get('name', ''),
            'picture': google_user_info.get('picture', ''),
            'google_id': google_user_info.get('sub') or google_user_info.get('id')
        }
        
        result = process_user(user_data, auth_provider='google')
        
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({
            'message': f'Đăng nhập Google thất bại: {str(e)}',
            'error': 'GOOGLE_CALLBACK_ERROR'
        }), 500
    
@auth_bp.route('/change-password', methods=['POST'])
@jwt_required()
def change_password():
    """Change user password"""
    try:
        current_user_email = get_jwt_identity()
        data = request.get_json()
        
        if not data or not all(k in data for k in ('current_password', 'new_password')):
            return jsonify({'message': 'Mật khẩu hiện tại và mật khẩu mới là bắt buộc'}), 400
        
        is_valid, message = validate_password(data['new_password'])
        if not is_valid:
            return jsonify({'message': message}), 400
        
        user_doc = db.users.find_one({'email': current_user_email})
        if not user_doc:
            return jsonify({'message': 'Không tìm thấy người dùng'}), 404
            
        if not user_doc.get('password'):
            return jsonify({'message': 'Không thể thay đổi mật khẩu cho tài khoản Google'}), 400
            
        if not check_password_hash(user_doc['password'], data['current_password']):
            return jsonify({'message': 'Mật khẩu hiện tại không chính xác'}), 401
        
        new_hashed_password = generate_password_hash(data['new_password']).decode('utf-8')
        
        db.users.update_one(
            {'email': current_user_email},
            {'$set': {'password': new_hashed_password}}
        )
        
        db.refresh_tokens.delete_many({'user_email': current_user_email})
        
        return jsonify({'message': 'Thay đổi mật khẩu thành công'}), 200
        
    except Exception as e:
        return jsonify({'message': f'Thay đổi mật khẩu thất bại: {str(e)}'}), 500


@auth_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    """Request password reset"""
    try:
        data = request.get_json()
        
        if not data or 'email' not in data:
            return jsonify({'message': 'Email là bắt buộc'}), 400
        
        email = data['email']
        
        # Gọi service xử lý
        success, message, error_code = request_password_reset_service(email)
        
        if success:
            return jsonify({'message': message, 'success': True}), 200
        else:
            return jsonify({'message': message, 'success': False, 'error': error_code}), 400 if error_code != 'INTERNAL_ERROR' else 500
        
    except Exception as e:
        return jsonify({
            'message': f'Yêu cầu khôi phục mật khẩu thất bại: {str(e)}',
            'success': False,
            'error': 'INTERNAL_ERROR'
        }), 500

@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    """Reset password using token"""
    try:
        data = request.get_json()
        
        if not data or not all(k in data for k in ('token', 'new_password')):
            return jsonify({'message': 'Token và mật khẩu mới là bắt buộc'}), 400
        
        token = data['token']
        new_password = data['new_password']
        
        # Gọi service xử lý
        success, message, error_code = reset_password_service(token, new_password)
        
        if success:
            return jsonify({'message': message, 'success': True}), 200
        else:
            return jsonify({'message': message, 'success': False, 'error': error_code}), 400 if error_code != 'INTERNAL_ERROR' else 500
        
    except Exception as e:
        return jsonify({
            'message': f'Đặt lại mật khẩu thất bại: {str(e)}',
            'success': False,
            'error': 'INTERNAL_ERROR'
        }), 500

@auth_bp.route('/verify-reset-token', methods=['POST'])
def verify_reset_token():
    """Verify if reset token is valid"""
    try:
        data = request.get_json()
        
        if not data or 'token' not in data:
            return jsonify({'message': 'Token là bắt buộc'}), 400
        
        token = data['token']
        
        # Gọi service xử lý
        success, message, email, error_code = verify_reset_token_service(token)
        
        if success:
            return jsonify({'message': message,'valid': True, 'email': email }), 200
        else:
            return jsonify({ 'message': message, 'valid': False, 'error': error_code }), 400 if error_code != 'INTERNAL_ERROR' else 500
        
    except Exception as e:
        return jsonify({ 'message': f'Xác thực token thất bại: {str(e)}', 'valid': False, 'error': 'INTERNAL_ERROR' }), 500