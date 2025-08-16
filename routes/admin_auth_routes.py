from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required
from flask_bcrypt import check_password_hash
from utils.token_utils import create_user_tokens
from validators.admin_validators import validate_forgot_password_data, validate_reset_password_data
from validators.auth_validators import validate_email
from database.mongodb import MongoDBConnection
from datetime import datetime
from services.admin_auth_service import (
    reset_admin_password_by_token, request_admin_password_reset
)


admin_auth_bp = Blueprint('admin_auth', __name__)
db = MongoDBConnection.get_primary_db()


@admin_auth_bp.route('/login', methods=['POST'])
def admin_login():
    try:
        data = request.get_json()
        if not data or not all(k in data for k in ('email', 'password')):
            return jsonify({'message': 'Không được để trống email và mật khẩu'}), 400

        if not validate_email(data['email']):
            return jsonify({'message': 'Email không đúng định dạng'}), 400

        admin = db.admins.find_one({'email': data['email']})
        if not admin:
            return jsonify({'message': 'Email không hợp lệ.'}), 401

        if not check_password_hash(admin['password'], data['password']):
            return jsonify({'message': 'Mật khẩu không hợp lệ.'}), 401

        if not admin.get('is_enabled', True):
            return jsonify({'message': 'Tài khoản này đã bị khóa'}), 403

        access_token, refresh_token = create_user_tokens(data['email'], auth_provider='admin')

        return jsonify({
            'message': 'Admin login successful',
            'access_token': access_token,
            'refresh_token': refresh_token,
            'admin': {
                'id': str(admin['_id']),
                'email': admin['email'],
                'fullname': admin.get('fullname', ''),
                'role': admin.get('role', 'ADMIN'),
                'is_enabled': admin.get('is_enabled', True)
            }
        }), 200

    except Exception as e:
        return jsonify({'message': f'Admin login failed: {str(e)}'}), 500


@admin_auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def admin_logout():
    try:
        current_admin = get_jwt_identity()
        db.refresh_tokens.delete_many({'email': current_admin})
        return jsonify({'message': 'Admin logout successful'}), 200
    except Exception as e:
        return jsonify({'message': f'Admin logout failed: {str(e)}'}), 500


@admin_auth_bp.route('/admin/refresh', methods=['POST'])
def admin_refresh():
    try:
        data = request.get_json()

        if not data or 'refresh_token' not in data:
            return jsonify({'message': 'Refresh token is required'}), 400

        refresh_token_doc = db.refresh_tokens.find_one({
            'refresh_token': data['refresh_token']
        })

        if not refresh_token_doc:
            return jsonify({'message': 'Invalid refresh token'}), 401

        if refresh_token_doc['expiration_time'] < datetime.utcnow():
            db.refresh_tokens.delete_one({'_id': refresh_token_doc['_id']})
            return jsonify({'message': 'Phiên đăng nhập đã hết hạn'}), 401

        admin_email = refresh_token_doc['email']

        admin_doc = db.admins.find_one({'email': admin_email})
        if not admin_doc or not admin_doc.get('is_enabled', True):
            return jsonify({'message': 'Admin not found or disabled'}), 401

        new_access_token = create_access_token(identity=admin_email)

        return jsonify({
            'access_token': new_access_token,
            'refresh_token': data['refresh_token'],
            'message': 'Token refreshed successfully'
        }), 200

    except Exception as e:
        return jsonify({'message': f'Token refresh failed: {str(e)}'}), 500
    
# ===== QUÊN MẬT KHẨU =====

# Gửi mail quên mật khẩu
@admin_auth_bp.route('/forgot-password', methods=['POST'])
def admin_forgot_password_route():
    data = request.get_json()
    is_valid, msg = validate_forgot_password_data(data)
    if not is_valid:
        return jsonify({'message': msg}), 400
    ok, message = request_admin_password_reset(data['email'])
    code = 200 if ok else 404
    return jsonify({'message': message}), code

# Đặt lại mật khẩu bằng token
@admin_auth_bp.route('/reset-password', methods=['POST'])
def admin_reset_password_route():
    data = request.get_json()
    is_valid, msg = validate_reset_password_data(data)
    if not is_valid:
        return jsonify({'message': msg}), 400
    ok, message = reset_admin_password_by_token(data['token'], data['new_password'])
    code = 200 if ok else 400
    return jsonify({'message': message}), code