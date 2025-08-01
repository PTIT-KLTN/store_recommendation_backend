from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required
from flask_bcrypt import check_password_hash
from utils.token_utils import create_user_tokens
from validators.auth_validators import validate_email
from database.mongodb import MongoDBConnection
from datetime import datetime
from services.admin_auth_service import change_admin_password_service

admin_auth_bp = Blueprint('admin_auth', __name__)
db = MongoDBConnection.get_primary_db()


@admin_auth_bp.route('/login', methods=['POST'])
def admin_login():
    try:
        data = request.get_json()
        if not data or not all(k in data for k in ('username', 'password')):
            return jsonify({'message': 'Username and password are required'}), 400

        # if not validate_email(data['username']):
        #     return jsonify({'message': 'Invalid username format'}), 400

        admin = db.admins.find_one({'username': data['username']})
        if not admin:
            return jsonify({'message': 'Tên đăng nhập không hợp lệ.'}), 401

        if not check_password_hash(admin['password'], data['password']):
            return jsonify({'message': 'Mật khẩu không hợp lệ.'}), 401

        if not admin.get('is_enabled', True):
            return jsonify({'message': 'Tài khoản này đã bị khóa'}), 403

        access_token, refresh_token = create_user_tokens(data['username'], auth_provider='admin')

        return jsonify({
            'message': 'Admin login successful',
            'access_token': access_token,
            'refresh_token': refresh_token,
            'admin': {
                'id': str(admin['_id']),
                'username': admin['username'],
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
        db.refresh_tokens.delete_many({'username': current_admin})
        return jsonify({'message': 'Admin logout successful'}), 200
    except Exception as e:
        return jsonify({'message': f'Admin logout failed: {str(e)}'}), 500


@admin_auth_bp.route('/change-password', methods=['POST'])
@jwt_required()
def change_admin_password():
    try:
        admin_username = get_jwt_identity()
        data = request.get_json() or {}
        current = data.get('current_password')
        new = data.get('new_password')

        # Đảm bảo truyền đủ params
        if not current or not new:
            return jsonify({'message': 'Current and new password are required'}), 400

        # Gọi service xử lý
        success, error = change_admin_password_service(admin_username, current, new)
        if not success:
            return jsonify({'message': error}), 400

        return jsonify({'message': 'Password changed successfully'}), 200

    except Exception as e:
        return jsonify({'message': f'Failed to change password: {str(e)}'}), 500


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
            return jsonify({'message': 'Refresh token expired'}), 401

        admin_username = refresh_token_doc['username']

        admin_doc = db.admins.find_one({'username': admin_username})
        if not admin_doc or not admin_doc.get('is_enabled', True):
            return jsonify({'message': 'Admin not found or disabled'}), 401

        new_access_token = create_access_token(identity=admin_username)

        return jsonify({
            'access_token': new_access_token,
            'refresh_token': data['refresh_token'],
            'message': 'Token refreshed successfully'
        }), 200

    except Exception as e:
        return jsonify({'message': f'Token refresh failed: {str(e)}'}), 500