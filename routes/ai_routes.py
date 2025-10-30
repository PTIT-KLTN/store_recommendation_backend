from flask import Blueprint, request, jsonify
from services.rabbitmq_service import rabbitmq_service
from services.ai_rabbitmq_client import get_ai_service_client
import uuid
import logging

logger = logging.getLogger(__name__)

ai_bp = Blueprint('ai', __name__)

@ai_bp.route('/text', methods=['POST'])
def process_text():
    try:
        data = request.get_json()
        description = data.get('description')
        
        message = {
            'modelType': 'text',
            'requestMessage': description
        }
        
        response = rabbitmq_service.send_message(message, timeout=25)
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
        
        # TODO: Upload to S3 and get URL
        # For now, using placeholder
        image_url = f"placeholder_{uuid.uuid4()}"
        
        message = {
            'modelType': 'image',
            'fileName': image_url
        }
        
        response = rabbitmq_service.send_message(message, timeout=15)
        return jsonify(response), 200
        
    except TimeoutError:
        return jsonify({'message': 'Request timeout'}), 504
    except Exception as e:
        return jsonify({'message': str(e)}), 500


@ai_bp.route('/recipe-analysis', methods=['POST'])
def analyze_recipe():
    """
    Analyze recipe using AI Service via RabbitMQ.
    
    Request body:
        {
            "user_input": "Tôi muốn ăn phở bò"
        }
    
    Response (Standardized - 10 fixed fields):
        {
            "status": "success|error|guardrail_blocked",
            "error": "string | null",
            "error_type": "string | null",
            "dish": {"name": "...", "prep_time": "...", "servings": ...},
            "cart": {"total_items": ..., "items": [...]} | null,
            "suggestions": [...],
            "similar_dishes": [...],
            "warnings": [...],
            "insights": [...],
            "guardrail": {...} | null
        }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'Request body is required'
            }), 400
        
        user_input = data.get('user_input')
        
        if not user_input:
            return jsonify({
                'success': False,
                'error': 'user_input is required'
            }), 400
        
        if not isinstance(user_input, str):
            return jsonify({
                'success': False,
                'error': 'user_input must be a string'
            }), 400
        
        user_input = user_input.strip()
        if not user_input:
            return jsonify({
                'success': False,
                'error': 'user_input cannot be empty'
            }), 400
        
        logger.info(f"🍲 Recipe analysis request: {user_input[:100]}...")
        
        # Get AI Service client
        client = get_ai_service_client()
        
        # Check connection
        if not client.is_connected():
            logger.warning("⚠️ AI Service client not connected, attempting reconnect...")
            try:
                client.reconnect()
            except Exception as reconnect_error:
                logger.error(f"❌ Failed to reconnect: {reconnect_error}")
                return jsonify({
                    'success': False,
                    'error': 'AI Service is currently unavailable. Please try again later.'
                }), 503
        
        # Send request to AI Service
        response = client.analyze_recipe(user_input)
        
        # AI Service có thể trả về 2 formats:
        # Format mới (flat): {"status": "...", "error": "...", "dish": {...}, ...}
        # Format cũ (nested): {"success": false, "result": {"status": "...", ...}}
        
        # Detect format và normalize
        if 'result' in response and isinstance(response['result'], dict):
            # Format cũ - extract từ result
            result = response['result']
            status = result.get('status', '')
        else:
            # Format mới - đã flat
            result = response
            status = response.get('status', '')
        
        # Nếu vẫn không có status, fallback check success field (legacy)
        if not status and response.get('success') is False:
            # Legacy format detection
            if 'guardrail' in result and result.get('guardrail', {}).get('triggered'):
                status = 'guardrail_blocked'
            else:
                status = 'error'
        
        # ============================================================
        # CASE 1: Guardrail Blocked (không log error)
        # ============================================================
        if status == 'guardrail_blocked':
            logger.info(f"🛡️ Guardrail blocked: {user_input[:50]}...")
            
            # Build response với 10 fields chuẩn
            return jsonify({
                'status': 'guardrail_blocked',
                'error': result.get('error', 'Nội dung vi phạm chính sách an toàn'),
                'error_type': 'guardrail_violation',
                'message': 'Yêu cầu không phù hợp hoặc vi phạm chính sách an toàn. Vui lòng thử lại với nội dung khác.',
                'dish': result.get('dish', {'name': ''}),
                'cart': result.get('cart'),
                'suggestions': result.get('suggestions', []),
                'similar_dishes': result.get('similar_dishes', []),
                'warnings': result.get('warnings', []),
                'insights': result.get('insights', []),
                'guardrail': result.get('guardrail')
            }), 400
        
        # ============================================================
        # CASE 2: Technical Errors (log error vào database)
        # ============================================================
        elif status == 'error':
            error_message = result.get('error', 'Unknown error from AI Service')
            error_type = result.get('error_type', 'unknown')
            dish_name = result.get('dish', {}).get('name', '')
            
            # Auto-detect error_type nếu chưa có
            if error_type == 'unknown':
                error_lower = error_message.lower()
                if 'không tìm thấy tên món' in error_lower or 'dish not found' in error_lower:
                    error_type = 'dish_not_found'
                elif 'không tìm thấy công thức' in error_lower or 'recipe not found' in error_lower:
                    error_type = 'recipe_not_found'
                elif 'không có nguyên liệu' in error_lower or 'no valid ingredients' in error_lower:
                    error_type = 'no_valid_ingredients'
                elif 'trích xuất' in error_lower or 'extraction' in error_lower:
                    error_type = 'extraction_failed'
            
            # Log error với error_type để phân tích
            logger.error(f"❌ AI Service error [{error_type}]: {error_message}")
            
            # Xác định user-friendly message theo error_type
            if error_type == 'dish_not_found':
                user_message = 'Không nhận diện được tên món ăn trong yêu cầu. Vui lòng nhập rõ hơn (ví dụ: "Tôi muốn ăn phở bò").'
                status_code = 400
            elif error_type == 'recipe_not_found':
                user_message = f'Hiện tại chưa có công thức cho món "{dish_name}". Vui lòng thử món khác.'
                status_code = 404
            elif error_type == 'no_valid_ingredients':
                user_message = 'Không thể phân tích danh sách nguyên liệu. Vui lòng thử lại hoặc chọn món khác.'
                status_code = 400
            elif error_type == 'extraction_failed':
                user_message = 'Lỗi hệ thống khi xử lý yêu cầu. Vui lòng thử lại sau.'
                status_code = 500
            else:
                # Unknown error type
                user_message = f'Có lỗi xảy ra khi xử lý yêu cầu: {error_message}'
                status_code = 500
            
            # Build response với 10 fields chuẩn
            return jsonify({
                'status': 'error',
                'error': error_message,
                'error_type': error_type,
                'message': user_message,
                'dish': result.get('dish', {'name': ''}),
                'cart': result.get('cart'),
                'suggestions': result.get('suggestions', []),
                'similar_dishes': result.get('similar_dishes', []),
                'warnings': result.get('warnings', []),
                'insights': result.get('insights', []),
                'guardrail': result.get('guardrail')
            }), status_code
        
        # ============================================================
        # CASE 3: Success (log info)
        # ============================================================
        elif status == 'success':
            dish_name = result.get('dish', {}).get('name', 'Unknown')
            cart_items = result.get('cart', {}).get('total_items', 0) if result.get('cart') else 0
            
            logger.info(f"✅ Recipe analysis successful: {dish_name} ({cart_items} items)")
            
            # Build response với 10 fields chuẩn
            return jsonify({
                'status': 'success',
                'error': None,
                'error_type': None,
                'dish': result.get('dish', {'name': ''}),
                'cart': result.get('cart'),
                'suggestions': result.get('suggestions', []),
                'similar_dishes': result.get('similar_dishes', []),
                'warnings': result.get('warnings', []),
                'insights': result.get('insights', []),
                'guardrail': result.get('guardrail')
            }), 200
        
        # ============================================================
        # CASE 4: Unexpected status value
        # ============================================================
        else:
            logger.error(f"❌ Unexpected status '{status}' from AI Service. Full response: {response}")
            return jsonify({
                'status': 'error',
                'error': 'Invalid response status from AI Service',
                'error_type': 'invalid_response',
                'message': 'Định dạng phản hồi từ AI Service không hợp lệ. Vui lòng thử lại.',
                'dish': {'name': ''},
                'cart': None,
                'suggestions': [],
                'similar_dishes': [],
                'warnings': [],
                'insights': [],
                'guardrail': None
            }), 500
        
    except TimeoutError as e:
        logger.error(f"⏱️ AI Service timeout: {e}")
        return jsonify({
            'success': False,
            'error': 'AI Service request timeout. The service is taking too long to respond. Please try again.'
        }), 504
    
    except Exception as e:
        logger.error(f"❌ Error calling AI Service: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'Internal server error: {str(e)}'
        }), 500


@ai_bp.route('/recipe-analysis/health', methods=['GET'])
def health_check_ai_service():
    """
    Check if AI Service is responsive.
    
    Response:
        {
            "status": "healthy" | "degraded" | "unhealthy",
            "ai_service": "connected" | "slow_response" | "disconnected",
            "connection": true/false,
            "error": "..." (if unhealthy)
        }
    """
    try:
        client = get_ai_service_client()
        
        # Check connection status
        is_connected = client.is_connected()
        
        if not is_connected:
            return jsonify({
                'status': 'unhealthy',
                'ai_service': 'disconnected',
                'connection': False
            }), 503
        
        # Send simple test request with short timeout
        try:
            test_response = client.analyze_recipe("test health check")
            
            return jsonify({
                'status': 'healthy',
                'ai_service': 'connected',
                'connection': True
            }), 200
            
        except TimeoutError:
            return jsonify({
                'status': 'degraded',
                'ai_service': 'slow_response',
                'connection': True
            }), 200
            
    except Exception as e:
        logger.error(f"❌ Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'ai_service': 'error',
            'connection': False,
            'error': str(e)
        }), 503