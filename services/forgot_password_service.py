# services/forgot_password_service.py
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import os
from database.mongodb import MongoDBConnection
from validators.auth_validators import validate_email, validate_password
from flask_bcrypt import generate_password_hash

_db = MongoDBConnection.get_primary_db()

def request_password_reset_service(email: str):
    """
    Service để xử lý yêu cầu reset mật khẩu
    Returns: (success: bool, message: str, error_code: str or None)
    """
    try:
        # 1. Validate email format
        if not validate_email(email):
            return False, "Invalid email format", "INVALID_EMAIL"
        
        email = email.strip().lower()
        
        # 2. Kiểm tra user có tồn tại không
        user = _db.users.find_one({'email': email})
        if not user:
            # Vẫn trả về success để tránh email enumeration attack
            return True, "If the email exists, a password reset link has been sent", None
        
        # 3. Kiểm tra nếu là Google account
        if not user.get('password'):
            return False, "Cannot reset password for Google account. Please login with Google.", "GOOGLE_ACCOUNT"
        
        # 4. Kiểm tra user có bị disable không
        if not user.get('is_enabled', True):
            return False, "Account is disabled. Please contact support.", "ACCOUNT_DISABLED"
        
        # 5. Tạo reset token
        reset_token = secrets.token_urlsafe(32)
        token_expiry = datetime.utcnow() + timedelta(hours=1)  # Token hết hạn sau 1 giờ
        
        # 6. Xóa các token cũ và lưu token mới
        _db.password_reset_tokens.delete_many({'email': email})
        _db.password_reset_tokens.insert_one({
            'email': email,
            'token': reset_token,
            'expiry': token_expiry,
            'used': False,
            'created_at': datetime.utcnow()
        })
        
        # 7. Gửi email reset password
        reset_link = f"{os.getenv('FRONTEND_URL', 'http://localhost:3000')}/reset-password?token={reset_token}"
        email_sent = send_reset_password_email(email, user.get('fullname', ''), reset_link)
        
        if not email_sent:
            return False, "Failed to send reset password email. Please try again later.", "EMAIL_SEND_FAILED"
        
        return True, "If the email exists, a password reset link has been sent", None
        
    except Exception as e:
        return False, f"Failed to process forgot password request: {str(e)}", "INTERNAL_ERROR"

def reset_password_service(token: str, new_password: str):
    """
    Service để reset mật khẩu bằng token
    Returns: (success: bool, message: str, error_code: str or None)
    """
    try:
        # 1. Validate new password
        is_valid, message = validate_password(new_password)
        if not is_valid:
            return False, message, "INVALID_PASSWORD"
        
        # 2. Kiểm tra token
        token_doc = _db.password_reset_tokens.find_one({
            'token': token,
            'used': False
        })
        
        if not token_doc:
            return False, "Invalid or expired reset token", "INVALID_TOKEN"
        
        # 3. Kiểm tra token hết hạn chưa
        if token_doc['expiry'] < datetime.utcnow():
            _db.password_reset_tokens.delete_one({'_id': token_doc['_id']})
            return False, "Reset token has expired. Please request a new one.", "TOKEN_EXPIRED"
        
        email = token_doc['email']
        
        # 4. Kiểm tra user còn tồn tại không
        user = _db.users.find_one({'email': email})
        if not user:
            return False, "User not found", "USER_NOT_FOUND"
        
        # 5. Kiểm tra user có bị disable không
        if not user.get('is_enabled', True):
            return False, "Account is disabled. Please contact support.", "ACCOUNT_DISABLED"
        
        # 6. Hash password mới
        new_hashed_password = generate_password_hash(new_password).decode('utf-8')
        
        # 7. Cập nhật password
        _db.users.update_one(
            {'email': email},
            {
                '$set': {
                    'password': new_hashed_password,
                    'updated_at': datetime.utcnow()
                }
            }
        )
        
        # 8. Đánh dấu token đã sử dụng
        _db.password_reset_tokens.update_one(
            {'_id': token_doc['_id']},
            {
                '$set': {
                    'used': True,
                    'used_at': datetime.utcnow()
                }
            }
        )
        
        # 9. Xóa tất cả refresh tokens của user để force logout
        _db.refresh_tokens.delete_many({'user_email': email})
        
        return True, "Password reset successfully. Please login with your new password.", None
        
    except Exception as e:
        return False, f"Failed to reset password: {str(e)}", "INTERNAL_ERROR"

def verify_reset_token_service(token: str):
    """
    Service để kiểm tra token có hợp lệ không
    Returns: (success: bool, message: str, email: str or None, error_code: str or None)
    """
    try:
        # 1. Kiểm tra token
        token_doc = _db.password_reset_tokens.find_one({
            'token': token,
            'used': False
        })
        
        if not token_doc:
            return False, "Invalid reset token", None, "INVALID_TOKEN"
        
        # 2. Kiểm tra token hết hạn chưa
        if token_doc['expiry'] < datetime.utcnow():
            _db.password_reset_tokens.delete_one({'_id': token_doc['_id']})
            return False, "Reset token has expired", None, "TOKEN_EXPIRED"
        
        # 3. Kiểm tra user còn tồn tại không
        user = _db.users.find_one({'email': token_doc['email']})
        if not user:
            return False, "User not found", None, "USER_NOT_FOUND"
        
        # 4. Kiểm tra user có bị disable không
        if not user.get('is_enabled', True):
            return False, "Account is disabled", None, "ACCOUNT_DISABLED"
        
        return True, "Token is valid", token_doc['email'], None
        
    except Exception as e:
        return False, f"Failed to verify token: {str(e)}", None, "INTERNAL_ERROR"

def send_reset_password_email(email: str, fullname: str, reset_link: str):
    """
    Helper function để gửi email reset password (Tiếng Việt đơn giản)
    Returns: bool - True nếu gửi thành công
    """
    try:
        # Cấu hình email từ environment variables
        smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        smtp_port = int(os.getenv('SMTP_PORT', '587'))
        smtp_username = os.getenv('SMTP_USERNAME')
        smtp_password = os.getenv('SMTP_PASSWORD')
        from_email = os.getenv('FROM_EMAIL', smtp_username)
        app_name = os.getenv('APP_NAME', 'Markendation')
        
        if not all([smtp_username, smtp_password]):
            print("SMTP credentials not configured")
            return False
        
        # Tạo email message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f'Đặt lại mật khẩu - {app_name}'
        msg['From'] = from_email
        msg['To'] = email
        
        # HTML email template đơn giản
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .content {{
                    background-color: #ffffff;
                    padding: 30px;
                    border: 1px solid #e5e7eb;
                }}
                .button {{
                    display: inline-block;
                    background-color: #16a34a;
                    color: white;
                    padding: 12px 24px;
                    text-decoration: none;
                    border-radius: 6px;
                    font-weight: bold;
                    margin: 20px 0;
                }}
                .footer {{
                    background-color: #f9fafb;
                    padding: 20px;
                    text-align: center;
                    font-size: 14px;
                    color: #6b7280;
                    border-radius: 0 0 8px 8px;
                }}
                .warning {{
                    background-color: #fef3c7;
                    color: #92400e;
                    padding: 15px;
                    border-radius: 6px;
                    margin: 20px 0;
                    border-left: 4px solid #f59e0b;
                }}
                .link-box {{
                    background-color: #f3f4f6;
                    padding: 15px;
                    border-radius: 6px;
                    margin: 20px 0;
                    word-break: break-all;
                    font-family: monospace;
                    font-size: 14px;
                }}
            </style>
        </head>
        <body>
            <div class="content">
                <h2>Xin chào {fullname or 'bạn'}!</h2>
                
                <p>Chúng tôi nhận được yêu cầu đặt lại mật khẩu cho tài khoản {app_name} của bạn.</p>
                
                <p>Truy cập vào đường link bên dưới để thiết lập lại mật khẩu:</p>
                <div class="link-box">{reset_link}</div>
                
                <div class="warning">
                    <strong>⏰ Quan trọng:</strong> Liên kết này sẽ hết hạn sau <strong>1 giờ</strong> vì lý do bảo mật.
                </div>
                
                <p><strong>Lưu ý:</strong> Nếu bạn không yêu cầu đặt lại mật khẩu, vui lòng bỏ qua email này. Mật khẩu của bạn sẽ không thay đổi.</p>
                
                <p>Nếu bạn cần hỗ trợ, vui lòng liên hệ với đội ngũ hỗ trợ của chúng tôi.</p>
                
                <p>Trân trọng,<br>Đội ngũ {app_name}</p>
            </div>
            
            <div class="footer">
                <p>Đây là email tự động. Vui lòng không trả lời email này.</p>
                <p>© 2025 {app_name}. Tất cả quyền được bảo lưu.</p>
            </div>
        </body>
        </html>
        """
        
        # Plain text version (tiếng Việt)
        text_body = f"""
        Đặt lại mật khẩu - {app_name}
        
        Xin chào {fullname or 'bạn'},

        Chúng tôi nhận được yêu cầu đặt lại mật khẩu cho tài khoản {app_name} của bạn.

        Vui lòng click vào liên kết bên dưới để tạo mật khẩu mới:
        {reset_link}

        QUAN TRỌNG: Liên kết này sẽ hết hạn sau 1 giờ vì lý do bảo mật.

        Nếu bạn không yêu cầu đặt lại mật khẩu, vui lòng bỏ qua email này. Mật khẩu của bạn sẽ không thay đổi.

        Nếu bạn cần hỗ trợ, vui lòng liên hệ với đội ngũ hỗ trợ của chúng tôi.

        Trân trọng,
        Đội ngũ {app_name}

        ---
        Đây là email tự động. Vui lòng không trả lời email này.
        © 2025 {app_name}. Tất cả quyền được bảo lưu.
        """
        
        # Attach parts
        msg.attach(MIMEText(text_body, 'plain'))
        msg.attach(MIMEText(html_body, 'html'))
        
        # Send email
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.send_message(msg)
        
        print(f"Email đặt lại mật khẩu đã gửi thành công đến {email}")
        return True
        
    except Exception as e:
        print(f"Gửi email đặt lại mật khẩu thất bại đến {email}: {str(e)}")
        return False
    
def cleanup_expired_tokens():
    """
    Helper function để dọn dẹp các token đã hết hạn
    Có thể chạy định kỳ bằng cron job
    """
    try:
        result = _db.password_reset_tokens.delete_many({
            'expiry': {'$lt': datetime.utcnow()}
        })
        print(f"Cleaned up {result.deleted_count} expired password reset tokens")
        return result.deleted_count
    except Exception as e:
        print(f"Failed to cleanup expired tokens: {str(e)}")
        return 0