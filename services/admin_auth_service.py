from database.mongodb import MongoDBConnection
from flask_bcrypt import check_password_hash, generate_password_hash
from validators.auth_validators import validate_password, validate_email
from datetime import datetime

_db = MongoDBConnection.get_primary_db()

def change_admin_password_service(email: str, current_password: str, new_password: str):
    # if not validate_email(email):
    #     return None, "Invalid email format"

    # 2. Lấy record admin
    admin = _db.admins.find_one({'email': email})
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
    _db.admins.update_one(
        {'email': email},
        {'$set': {
            'password': new_hashed,
            'updated_at': datetime.utcnow()
        }}
    )

    # 7. Xóa refresh tokens
    _db.refresh_tokens.delete_many({'email': email})

    return True, None