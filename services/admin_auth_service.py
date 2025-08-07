from database.mongodb import MongoDBConnection
from flask_bcrypt import check_password_hash, generate_password_hash
from validators.auth_validators import validate_password, validate_email
from datetime import datetime
import uuid
from datetime import timedelta
from services.forgot_password_service import send_reset_password_email

db = MongoDBConnection.get_primary_db()

def change_admin_password_service(email: str, current_password: str, new_password: str):
    if not validate_email(email):
        return None, "Invalid email format"

    # 2. Lấy record admin
    admin = db.admins.find_one({'email': email})
    if not admin:
        return None, "Tên đăng nhập không hợp lệ"

    # 3. New không được trùng old
    if current_password == new_password:
        return None, "Mật khẩu mới không được trùng với mật khẩu cũ"

    # 4. Kiểm tra old password
    if not check_password_hash(admin['password'], current_password):
        return None, "Mật khẩu cũ không chính xác"

    # 5. Validate new password
    is_valid, msg = validate_password(new_password)
    if not is_valid:
        return None, msg

    # 6. Hash và update
    new_hashed = generate_password_hash(new_password).decode('utf-8')
    db.admins.update_one(
        {'email': email},
        {'$set': {
            'password': new_hashed,
            'updated_at': datetime.utcnow()
        }}
    )

    # 7. Xóa refresh tokens
    db.refresh_tokens.delete_many({'email': email})

    return True, None

def generate_reset_token():
    return str(uuid.uuid4())

def create_password_reset_token(email, role):
    token = generate_reset_token()
    expires_at = datetime.utcnow() + timedelta(minutes=5)

    # Xóa token cũ cùng email, role (nếu có)
    db.password_reset_tokens.delete_many({'email': email, 'role': role})

    db.password_reset_tokens.insert_one({
        'email': email,
        'token': token,
        'role': role,
        'expiry': expires_at,
        'used': False,
        'created_at': datetime.utcnow()
    })
    return token

def request_admin_password_reset(email):
    admin = db.admins.find_one({'email': email})
    if not admin:
        return False, "Không tìm thấy admin với email này"
    token = create_password_reset_token(email, "ADMIN")
    reset_link = f"http://localhost:3000/reset-password?token={token}&role=ADMIN"
    send_reset_password_email(email, admin.get('fullname', ''), reset_link)
    return True, "Link reset mật khẩu được gửi thành công"

from flask_bcrypt import check_password_hash
def reset_admin_password_by_token(token, new_password):

    doc = db.password_reset_tokens.find_one({'token': token, 'role': 'ADMIN'})
    if not doc:
        return False, "Token đã hết hạn hoặc không hợp lệ."
    if doc['expiry'] < datetime.utcnow():
        return False, "Token đã hết hạn"

    admin = db.admins.find_one({'email': doc['email']})

    # Kiểm tra mật khẩu mới có trùng mật khẩu cũ không
    if admin and check_password_hash(admin['password'], new_password):
        return False, "Mật khẩu mới không được trùng với mật khẩu cũ."

    hashed_pw = generate_password_hash(new_password).decode('utf-8')
    db.admins.update_one(
        {'email': doc['email']},
        {'$set': {'password': hashed_pw, 'updated_at': datetime.utcnow()}}
    )
    db.password_reset_tokens.update_one(
        {'_id': doc['_id']},
        {'$set': {'used': True, 'used_at': datetime.utcnow()}}
    )
    return True, "Mật khẩu được đổi thành công."
