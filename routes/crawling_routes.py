from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from services.rabbitmq_service import rabbitmq_service
from datetime import datetime
from middleware.admin_middleware import admin_required

crawling_bp = Blueprint('crawling', __name__)

def get_user_or_401():
    """Get current user"""
    user = get_jwt_identity()
    if not user:
        return None
    return user

def make_response(message, data=None, status=200, **metadata):
    """Create consistent responses"""
    response = {
        'message': message,
        'data': data,
        'metadata': {
            'timestamp': datetime.utcnow().isoformat(),
            **metadata
        }
    }
    return jsonify(response), status

@crawling_bp.route('/ping', methods=['GET'])
@jwt_required()
@admin_required
def ping():
    """Test crawling service"""
    current_user_email = get_jwt_identity()
    if not current_user_email:
        return jsonify({'message': 'Invalid token'}), 401
    
    try:
        response = rabbitmq_service.send_request('ping', timeout=10)
        return make_response('Crawling service available', response, requestedBy=current_user_email)
    except TimeoutError:
        return make_response('Service timeout', None, 503, error='TIMEOUT')
    except Exception as e:
        return make_response(f'Connection error: {str(e)}', None, 500, error='SERVER_ERROR')

@crawling_bp.route('/crawl/store', methods=['POST'])
@jwt_required()
def crawl_store():
    """Crawl specific store"""
    user = get_user_or_401()
    if not user:
        return jsonify({'message': 'Invalid token'}), 401
    
    data = request.get_json() or {}
    
    # Validation
    store_id = data.get('storeId')
    chain = data.get('chain', 'BHX').upper()
    
    if not store_id:
        return make_response('storeId required', None, 400, error='VALIDATION_ERROR')
    
    if chain not in ['BHX', 'WM']:
        return make_response('chain must be BHX or WM', None, 400, error='VALIDATION_ERROR')
    
    try:
        timeout = 60 if data.get('onlyOneProduct') else 300
        
        response = rabbitmq_service.send_request('crawl_store', {
            'storeId': store_id,
            'chain': chain,
            'provinceId': data.get('provinceId', 3),
            'onlyOneProduct': data.get('onlyOneProduct', False)
        }, timeout=timeout)
        
        return make_response(
            f'{chain} store crawling completed', 
            response, 
            storeId=store_id, 
            chain=chain, 
            requestedBy=user
        )
    except TimeoutError:
        return make_response('Crawling timeout', None, 504, error='TIMEOUT')
    except Exception as e:
        return make_response(f'Error: {str(e)}', None, 500, error='SERVER_ERROR')

@crawling_bp.route('/search', methods=['POST'])
@jwt_required()
def search_products():
    """Search products across chains"""
    user = get_user_or_401()
    if not user:
        return jsonify({'message': 'Invalid token'}), 401
    
    data = request.get_json() or {}
    
    # Validation
    query = data.get('query', '').strip()
    max_results = data.get('maxResults', 20)
    chain = data.get('chain', 'ALL').upper()
    
    if not query or len(query) < 2:
        return make_response('Query must be at least 2 characters', None, 400, error='VALIDATION_ERROR')
    
    if not isinstance(max_results, int) or not (1 <= max_results <= 100):
        return make_response('Max results must be 1-100', None, 400, error='VALIDATION_ERROR')
    
    try:
        response = rabbitmq_service.send_request('search_products', {
            'query': query,
            'maxResults': max_results,
            'category': data.get('category', ''),
            'chain': chain
        }, timeout=30)
        
        return make_response(
            f'Search completed for {chain}', 
            response, 
            query=query, 
            chain=chain, 
            maxResults=max_results, 
            requestedBy=user
        )
    except TimeoutError:
        return make_response('Search timeout', None, 504, error='TIMEOUT')
    except Exception as e:
        return make_response(f'Error: {str(e)}', None, 500, error='SERVER_ERROR')