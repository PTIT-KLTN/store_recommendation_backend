import uuid
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from services.rabbitmq_service import rabbitmq_service
from datetime import datetime
from middleware.admin_middleware import admin_required
from database.mongodb import MongoDBConnection
import pymongo
import os

schedule_bp = Blueprint('schedule', __name__)
db = MongoDBConnection.get_primary_db()
metadata_db = MongoDBConnection.get_metadata_db()

def make_response(message, data=None, status=200, **metadata):
    return jsonify({
        'message': message,
        'data': data,
        'metadata': {'timestamp': datetime.utcnow().isoformat(), **metadata}
    }), status

@schedule_bp.route('/crawl/schedule', methods=['POST'])
@jwt_required()
def create_crawl_schedule():
    """Create crawling schedule for all stores"""
    user = get_jwt_identity()
    if not user:
        return jsonify({'message': 'Invalid token'}), 401

    data = request.get_json() or {}
    
    # Validation - không cần storeId nữa
    required_fields = ['name', 'scheduleType']
    for field in required_fields:
        if not data.get(field):
            return make_response(f'{field} is required', None, 400)
    
    schedule_id = str(uuid.uuid4())
    current_time = datetime.utcnow()
    
    schedule_record = {
        'schedule_id': schedule_id,
        'user_id': user,
        'name': data['name'],
        'crawl_all_stores': True,  # Flag để crawl tất cả stores
        'chains': data.get('chains', ['BHX', 'WM']),  # Mặc định crawl cả 2 chuỗi
        'schedule_type': data['scheduleType'],  # 'hourly', 'daily', 'weekly'
        'schedule_config': {
            'hour': data.get('hour'),
            'minute': data.get('minute', 0),
            'day_of_week': data.get('dayOfWeek'),  # 0-6 for weekly
        },
        'parameters': {
            'concurrency': data.get('concurrency', 2)  # Giảm concurrency cho crawl nhiều stores
        },
        'is_active': True,
        'created_at': current_time,
        'updated_at': current_time
    }
    
    try:
        # Save to database  
        db.crawling_schedules.insert_one(schedule_record)
        
        schedule_info = {
            'type': 'schedule',
            'schedule_id': schedule_id,
            'schedule_type': data['scheduleType'],
            'schedule_config': {
                'hour': data.get('hour'),
                'minute': data.get('minute', 0), 
                'day_of_week': data.get('dayOfWeek'),
            },
            'chains': data.get('chains', ['BHX', 'WM']),
            'concurrency': data.get('concurrency', 2),
            'is_active': True,
            'created_at': current_time
        }

        metadata_db.schedule_configs.insert_one(schedule_info)
        
        return make_response(
            'All stores crawling schedule created successfully',
            {
                'schedule_id': schedule_id,
                'name': data['name'],
                'chains': schedule_record['chains'],
                'status': 'created'
            },
            201
        )
        
    except Exception as e:
        return make_response(f'Error: {str(e)}', None, 500)

@schedule_bp.route('/schedules', methods=['GET'])
@jwt_required()
def get_user_schedules():
    """Get user's crawling schedules"""
    user = get_jwt_identity()
    if not user:
        return jsonify({'message': 'Invalid token'}), 401
    
    try:
        schedules = list(
            db.crawling_schedules.find({'user_id': user})
            .sort('created_at', -1)
        )
        
        # Convert datetime objects to ISO strings and ObjectId to string
        for schedule in schedules:
            schedule['_id'] = str(schedule['_id'])
            if 'created_at' in schedule:
                schedule['created_at'] = schedule['created_at'].isoformat() if hasattr(schedule['created_at'], 'isoformat') else schedule['created_at']
            if 'updated_at' in schedule:
                schedule['updated_at'] = schedule['updated_at'].isoformat() if hasattr(schedule['updated_at'], 'isoformat') else schedule['updated_at']
        
        return make_response('Schedules retrieved', {'schedules': schedules})
        
    except Exception as e:
        return make_response(f'Error: {str(e)}', None, 500)

@schedule_bp.route('/schedule/<schedule_id>', methods=['DELETE'])
@jwt_required()
def delete_schedule(schedule_id):
    """Delete crawling schedule"""
    user = get_jwt_identity()
    if not user:
        return jsonify({'message': 'Invalid token'}), 401
    
    try:
        schedule = db.crawling_schedules.find_one({'schedule_id': schedule_id, 'user_id': user})
        if not schedule:
            return make_response('Schedule not found', None, 404)
        
        # Deactivate schedule  
        db.crawling_schedules.update_one(
            {'schedule_id': schedule_id},
            {'$set': {'is_active': False, 'updated_at': datetime.utcnow()}}
        )
        
        metadata_db.schedule_configs.update_one(
            {'schedule_id': schedule_id},
            {'$set': {'is_active': False}}
        )
        
        return make_response('Schedule deleted successfully')
        
    except Exception as e:
        return make_response(f'Error: {str(e)}', None, 500)