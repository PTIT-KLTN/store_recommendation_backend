from flask import Blueprint, request, jsonify
from services.rabbitmq_service import rabbitmq_service
from services.ai_rabbitmq_client import get_ai_service_client
from services.s3_service import get_s3_service
from services.allergy_service import get_allergy_service
from utils.token_utils import decode_token
import logging

logger = logging.getLogger(__name__)

ai_bp = Blueprint('ai', __name__)


def get_current_user_email():
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return None
        
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            return None
        
        token = parts[1]
        user_data = decode_token(token)
        return user_data.get('email') if user_data else None
    except Exception:
        return None


def apply_allergy_filter(result: dict) -> dict:
    user_email = get_current_user_email()
    cart = result.get('cart')
    warnings = list(result.get('warnings', []))
    
    if user_email and cart and cart.get('items'):
        allergy_service = get_allergy_service()
        user_allergies = allergy_service.get_user_allergies(user_email)
        
        if user_allergies:
            filter_result = allergy_service.filter_cart_items(cart['items'], user_allergies)
            cart['items'] = filter_result['filtered_items']
            cart['total_items'] = len(filter_result['filtered_items'])
            warnings.extend(filter_result['allergy_warnings'])
    
    result['cart'] = cart
    result['warnings'] = warnings
    return result


def normalize_response(response: dict) -> tuple:
    """Normalize AI Service response format and detect status"""
    if 'result' in response and isinstance(response['result'], dict):
        result = response['result']
        status = result.get('status', '')
    else:
        result = response
        status = response.get('status', '')
    
    if not status and response.get('success') is False:
        if 'guardrail' in result and result.get('guardrail', {}).get('triggered'):
            status = 'guardrail_blocked'
        else:
            status = 'error'
    
    return result, status


def get_error_message(error_type: str, dish_name: str = '') -> tuple:
    """Get user-friendly error message and status code"""
    messages = {
        'dish_not_found': ('Không nhận diện được tên món ăn trong yêu cầu. Vui lòng nhập rõ hơn.', 400),
        'recipe_not_found': (f'Hiện tại chưa có công thức cho món "{dish_name}". Vui lòng thử món khác.', 404),
        'no_valid_ingredients': ('Không thể phân tích danh sách nguyên liệu. Vui lòng thử lại.', 400),
        'extraction_failed': ('Lỗi hệ thống khi xử lý yêu cầu. Vui lòng thử lại sau.', 500),
        'image_download_failed': ('Không thể tải hình ảnh. Vui lòng kiểm tra lại URL.', 400),
    }
    return messages.get(error_type, (f'Có lỗi xảy ra khi xử lý yêu cầu.', 500))


def build_standard_response(status: str, result: dict, error_msg: str = None, user_msg: str = None) -> dict:
    """Build standardized 10-field response"""
    return {
        'status': status,
        'error': error_msg,
        'error_type': result.get('error_type') if status == 'error' else None,
        'message': user_msg,
        'dish': result.get('dish', {'name': ''}),
        'cart': result.get('cart'),
        'suggestions': result.get('suggestions', []),
        'similar_dishes': result.get('similar_dishes', []),
        'warnings': result.get('warnings', []),
        'insights': result.get('insights', []),
        'guardrail': result.get('guardrail')
    }


def detect_error_type(error_message: str, is_image: bool = False) -> str:
    """Auto-detect error type from error message"""
    error_lower = error_message.lower()
    
    if is_image and ('s3' in error_lower or 'download' in error_lower or 'image' in error_lower):
        return 'image_download_failed'
    elif 'không tìm thấy tên món' in error_lower or 'dish not found' in error_lower:
        return 'dish_not_found'
    elif 'không tìm thấy công thức' in error_lower or 'recipe not found' in error_lower:
        return 'recipe_not_found'
    elif 'không có nguyên liệu' in error_lower or 'no valid ingredients' in error_lower:
        return 'no_valid_ingredients'
    elif 'trích xuất' in error_lower or 'extraction' in error_lower:
        return 'extraction_failed'
    
    return 'unknown'

@ai_bp.route('/text', methods=['POST'])
def process_text():
    try:
        data = request.get_json()
        description = data.get('description')
        
        message = {
            'modelType': 'text',
            'requestMessage': description
        }
        
        response = rabbitmq_service.send_message(message, timeout=100)
        return jsonify(response), 200
        
    except TimeoutError:
        return jsonify({'message': 'Request timeout'}), 504
    except Exception as e:
        return jsonify({'message': str(e)}), 500

@ai_bp.route('/image', methods=['POST'])
def process_image():
    try:
        if 'image' not in request.files:
            return jsonify({'message': 'No image file provided'}), 400
        
        file = request.files['image']
        if file.filename == '':
            return jsonify({'message': 'No file selected'}), 400
        
        try:
            s3_service = get_s3_service()
            s3_key = s3_service.upload_image(file=file, filename=file.filename, content_type=file.content_type)
        except Exception as e:
            logger.error(f"Failed to upload image: {e}")
            return jsonify({'message': f'Failed to upload image: {str(e)}'}), 500
        
        message = {
            'modelType': 'image',
            'fileName': s3_key
        }
        
        response = rabbitmq_service.send_message(message, timeout=100)
        return jsonify(response), 200
        
    except TimeoutError:
        return jsonify({'message': 'Request timeout'}), 504
    except Exception as e:
        return jsonify({'message': str(e)}), 500


@ai_bp.route('/recipe-analysis', methods=['POST'])
def analyze_recipe():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Request body is required'}), 400
        
        user_input = data.get('user_input')
        if not user_input or not isinstance(user_input, str):
            return jsonify({'success': False, 'error': 'user_input is required'}), 400
        
        user_input = user_input.strip()
        if not user_input:
            return jsonify({'success': False, 'error': 'user_input cannot be empty'}), 400
        
        client = get_ai_service_client()
        
        if not client.is_connected():
            try:
                client.reconnect()
            except Exception as e:
                logger.error(f"Failed to reconnect: {e}")
                return jsonify({'success': False, 'error': 'AI Service unavailable'}), 503
        
        response = client.analyze_recipe(user_input)
        result, status = normalize_response(response)
        
        if status == 'guardrail_blocked':
            return jsonify(build_standard_response(
                'guardrail_blocked', 
                result,
                result.get('error', 'Nội dung vi phạm chính sách an toàn'),
                'Yêu cầu không phù hợp. Vui lòng thử lại với nội dung khác.'
            )), 400
        
        elif status == 'error':
            error_message = result.get('error', 'Unknown error')
            error_type = result.get('error_type', 'unknown')
            
            if error_type == 'unknown':
                error_type = detect_error_type(error_message)
            
            logger.error(f"AI Service error [{error_type}]: {error_message}")
            
            user_message, status_code = get_error_message(error_type, result.get('dish', {}).get('name', ''))
            
            return jsonify(build_standard_response('error', result, error_message, user_message)), status_code
        
        elif status == 'success':
            result = apply_allergy_filter(result)
            return jsonify(build_standard_response('success', result)), 200
        
        else:
            logger.error(f"Unexpected status '{status}'")
            return jsonify(build_standard_response(
                'error',
                {'dish': {'name': ''}, 'cart': None},
                'Invalid response status',
                'Định dạng phản hồi không hợp lệ'
            )), 500
        
    except TimeoutError:
        logger.error("AI Service timeout")
        return jsonify({'success': False, 'error': 'Request timeout'}), 504
    
    except Exception as e:
        logger.error(f"Error calling AI Service: {e}", exc_info=True)
        return jsonify({'success': False, 'error': f'Internal server error: {str(e)}'}), 500


@ai_bp.route('/recipe-analysis/health', methods=['GET'])
def health_check_ai_service():
    try:
        client = get_ai_service_client()
        is_connected = client.is_connected()
        
        if not is_connected:
            return jsonify({'status': 'unhealthy', 'ai_service': 'disconnected', 'connection': False}), 503
        
        try:
            client.analyze_recipe("test health check")
            return jsonify({'status': 'healthy', 'ai_service': 'connected', 'connection': True}), 200
        except TimeoutError:
            return jsonify({'status': 'degraded', 'ai_service': 'slow_response', 'connection': True}), 200
            
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({'status': 'unhealthy', 'ai_service': 'error', 'connection': False, 'error': str(e)}), 503


@ai_bp.route('/image-analysis', methods=['POST'])
def analyze_image():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Request body is required'}), 400
        
        s3_url = data.get('s3_url')
        if not s3_url or not isinstance(s3_url, str):
            return jsonify({'success': False, 'error': 's3_url is required'}), 400
        
        s3_url = s3_url.strip()
        if not s3_url:
            return jsonify({'success': False, 'error': 's3_url cannot be empty'}), 400
        
        description = data.get('description', '')
        if description and not isinstance(description, str):
            return jsonify({'success': False, 'error': 'description must be a string'}), 400
        
        client = get_ai_service_client()
        
        if not client.is_connected():
            try:
                client.reconnect()
            except Exception as e:
                logger.error(f"Failed to reconnect: {e}")
                return jsonify({'success': False, 'error': 'AI Service unavailable'}), 503
        
        response = client.analyze_image(s3_url, description)
        result, status = normalize_response(response)
        
        if status == 'guardrail_blocked':
            return jsonify(build_standard_response(
                'guardrail_blocked',
                result,
                result.get('error', 'Hình ảnh vi phạm chính sách an toàn'),
                'Hình ảnh không phù hợp. Vui lòng thử lại với hình ảnh khác.'
            )), 400
        
        elif status == 'error':
            error_message = result.get('error', 'Unknown error')
            error_type = result.get('error_type', 'unknown')
            
            if error_type == 'unknown':
                error_type = detect_error_type(error_message, is_image=True)
            
            logger.error(f"AI Service error [{error_type}]: {error_message}")
            
            user_message, status_code = get_error_message(error_type, result.get('dish', {}).get('name', ''))
            
            return jsonify(build_standard_response('error', result, error_message, user_message)), status_code
        
        elif status == 'success':
            return jsonify(build_standard_response('success', result)), 200
        
        else:
            logger.error(f"Unexpected status '{status}'")
            return jsonify(build_standard_response(
                'error',
                {'dish': {'name': ''}, 'cart': None},
                'Invalid response status',
                'Định dạng phản hồi không hợp lệ'
            )), 500
        
    except TimeoutError:
        logger.error("AI Service timeout")
        return jsonify({'success': False, 'error': 'Request timeout'}), 504
    
    except Exception as e:
        logger.error(f"Error calling AI Service for image: {e}", exc_info=True)
        return jsonify({'success': False, 'error': f'Internal server error: {str(e)}'}), 500


@ai_bp.route('/upload-and-analyze', methods=['POST'])
def upload_and_analyze():
    try:
        if 'image' not in request.files:
            return jsonify({'success': False, 'error': 'Image file is required'}), 400
        
        file = request.files['image']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400
        
        allowed_extensions = {'jpg', 'jpeg', 'png', 'webp', 'gif', 'bmp', 'tiff', 'tif'}
        file_ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
        
        if file_ext not in allowed_extensions:
            return jsonify({'success': False, 'error': f'Invalid file type. Allowed: {", ".join(allowed_extensions)}'}), 400
        
        file.seek(0, 2)
        file_size = file.tell()
        file.seek(0)
        
        max_size = 10 * 1024 * 1024
        if file_size > max_size:
            return jsonify({'success': False, 'error': f'File too large. Maximum size: {max_size / (1024*1024)}MB'}), 400
        
        description = request.form.get('description', '')
        
        try:
            s3_service = get_s3_service()
            s3_key = s3_service.upload_image(file=file, filename=file.filename, content_type=file.content_type)
        except Exception as e:
            logger.error(f"Failed to upload image: {e}")
            return jsonify({'success': False, 'error': f'Failed to upload image: {str(e)}'}), 500
        
        client = get_ai_service_client()
        
        if not client.is_connected():
            try:
                client.reconnect()
            except Exception as e:
                logger.error(f"Failed to reconnect: {e}")
                s3_service.delete_image(s3_key)
                return jsonify({'success': False, 'error': 'AI Service unavailable'}), 503
        
        response = client.analyze_image(s3_key, description)
        result, status = normalize_response(response)
        
        response_with_key = lambda resp: {**resp, 's3_key': s3_key if status != 'guardrail_blocked' else None}
        
        if status == 'guardrail_blocked':
            s3_service.delete_image(s3_key)
            return jsonify(response_with_key(build_standard_response(
                'guardrail_blocked',
                result,
                result.get('error', 'Hình ảnh vi phạm chính sách an toàn'),
                'Hình ảnh không phù hợp. Vui lòng thử lại với hình ảnh khác.'
            ))), 400
        
        elif status == 'error':
            error_message = result.get('error', 'Unknown error')
            error_type = result.get('error_type', 'unknown')
            
            if error_type == 'unknown':
                error_type = detect_error_type(error_message, is_image=True)
            
            logger.error(f"AI Service error [{error_type}]: {error_message}")
            user_message, status_code = get_error_message(error_type, result.get('dish', {}).get('name', ''))
            
            return jsonify(response_with_key(build_standard_response('error', result, error_message, user_message))), status_code
        
        elif status == 'success':
            return jsonify(response_with_key(build_standard_response('success', result))), 200
        
        else:
            logger.error(f"Unexpected status '{status}'")
            return jsonify(response_with_key(build_standard_response(
                'error',
                {'dish': {'name': ''}, 'cart': None},
                'Invalid response status',
                'Định dạng phản hồi không hợp lệ'
            ))), 500
        
    except TimeoutError:
        logger.error("AI Service timeout")
        return jsonify({'success': False, 'error': 'Request timeout'}), 504
    
    except Exception as e:
        logger.error(f"Error in upload and analyze: {e}", exc_info=True)
        return jsonify({'success': False, 'error': f'Internal server error: {str(e)}'}), 500
