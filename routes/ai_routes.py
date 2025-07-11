from flask import Blueprint, request, jsonify
from services.rabbitmq_service import rabbitmq_service
import uuid

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