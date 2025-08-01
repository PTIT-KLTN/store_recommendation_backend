import re

def validate_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_password(password):
    if len(password) < 5:
        return False, "Mật khẩu phải có ít nhất 5 ký tự"
    return True, "Password is valid"

def validate_username(username):
    if len(username) < 5:
        return False, "Tên đăng nhập phải có ít nhất 5 ký tự"
    if not re.match(r'^[A-Za-z0-9]+$', username):
        return False, "Username chỉ được bao gồm chữ và số, không được có dấu cách hoặc ký tự đặc biệt"
    return True, "Username is valid"