import uuid
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from services.rabbitmq_service import rabbitmq_service
from datetime import datetime
from middleware.admin_middleware import admin_required
from database.mongodb import MongoDBConnection

crawling_bp = Blueprint('crawling', __name__)
db = MongoDBConnection.get_primary_db()


def get_user_or_401():
    user = get_jwt_identity()
    return user if user else None

def make_response(message, data=None, status=200, **metadata):
    return jsonify({
        'message': message,
        'data': data,
        'metadata': {'timestamp': datetime.utcnow().isoformat(), **metadata}
    }), status

@crawling_bp.route('/ping', methods=['GET'])
@jwt_required()
@admin_required
def ping():
    """Test crawling service"""
    current_user_email = get_jwt_identity()
    if not current_user_email:
        return jsonify({'message': 'Invalid token'}), 401
    
    try:
        response = rabbitmq_service.send_request('ping', timeout=30)
        return make_response('Crawling service available', response, requestedBy=current_user_email)
    except TimeoutError:
        return make_response('Service timeout', None, 503, error='TIMEOUT')
    except Exception as e:
        return make_response(f'Connection error: {str(e)}', None, 500, error='SERVER_ERROR')

@crawling_bp.route('/crawl/store', methods=['POST'])
@jwt_required()
def crawl_store():
    """Start store crawling (async pattern)"""
    user = get_user_or_401()
    if not user:
        return jsonify({'message': 'Invalid token'}), 401

    data = request.get_json() or {}
    store_id = data.get('storeId')
    chain = data.get('chain', 'BHX').upper()

    if not store_id:
        return make_response('storeId required', None, 400)

    # Generate task ID
    task_id = str(uuid.uuid4())
    
    # Create task record in database
    task_record = {
        'task_id': task_id,
        'user_id': user,
        'store_id': store_id,
        'chain': chain,
        'status': 'queued',
        'created_at': datetime.utcnow(),
        'updated_at': datetime.utcnow(),
        'parameters': {
            'provinceId': data.get('provinceId', 3),
            'districtId': data.get('districtId', 0),
            'wardId': data.get('wardId', 0),
            'concurrency': data.get('concurrency', 3)
        }
    }
    
    try:
        # Save task to database
        db.crawling_tasks.insert_one(task_record)
        
        # Send async request to crawling service
        payload = {
            'task_id': task_id,
            'chain': chain,
            'storeId': store_id,
            **task_record['parameters']
        }
        
        # Fire and forget - don't wait for response
        rabbitmq_service.send_async_request('crawl_store', payload)
        
        return make_response(
            f'{chain} store crawling started',
            {
                'task_id': task_id,
                'status': 'queued',
                'store_id': store_id,
                'chain': chain,
                'check_status_url': f'/api/v1/crawling/task/{task_id}/status'
            },
            202
        )
        
    except Exception as e:
        return make_response(f'Error: {str(e)}', None, 500)

@crawling_bp.route('/task/<task_id>/status', methods=['GET'])
@jwt_required()
def get_task_status(task_id):
    """Get crawling task status"""
    user = get_user_or_401()
    if not user:
        return jsonify({'message': 'Invalid token'}), 401
    
    try:
        task = db.crawling_tasks.find_one({'task_id': task_id})
        
        if not task:
            return make_response('Task not found', None, 404)
        
        if task.get('user_id') != user:
            return make_response('Access denied', None, 403)
        
        # Convert ObjectId to string
        if '_id' in task:
            task['_id'] = str(task['_id'])
        
        return make_response('Task status retrieved', task)
        
    except Exception as e:
        return make_response(f'Error: {str(e)}', None, 500)

@crawling_bp.route('/tasks', methods=['GET'])
@jwt_required()
def get_user_tasks():
    """Get user's crawling tasks"""
    user = get_user_or_401()
    if not user:
        return jsonify({'message': 'Invalid token'}), 401
    
    try:
        limit = int(request.args.get('limit', 20))
        skip = int(request.args.get('skip', 0))
        status = request.args.get('status')
        
        query = {'user_id': user}
        if status:
            query['status'] = status
        
        tasks = list(
            db.crawling_tasks.find(query)
            .sort('created_at', -1)
            .skip(skip)
            .limit(limit)
        )
        
        for task in tasks:
            if '_id' in task:
                task['_id'] = str(task['_id'])
        
        total = db.crawling_tasks.count_documents(query)
        
        return make_response('Tasks retrieved', {
            'tasks': tasks,
            'total': total,
            'limit': limit,
            'skip': skip
        })
        
    except Exception as e:
        return make_response(f'Error: {str(e)}', None, 500)