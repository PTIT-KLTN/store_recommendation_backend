# crawling_routes.py
import os
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
from middleware.admin_middleware import admin_required
from services.crawler_celery import celery_crawler

crawling_bp = Blueprint('crawling', __name__)

def make_response(msg, data=None, status=200, **meta):
    return jsonify({
        'message': msg,
        'data': data,
        'meta': { 'timestamp': datetime.utcnow().isoformat(), **meta }
    }), status

@crawling_bp.route('/ping', methods=['GET'])
@jwt_required()
@admin_required
def ping():
    user = get_jwt_identity()
    try:
        workers = celery_crawler.control.ping(timeout=10)
        return make_response('pong', {'workers': workers}, 200, requestedBy=user)
    except Exception as e:
        return make_response('Crawling service unavailable', None, 503, error=str(e))

@crawling_bp.route('/crawl/store', methods=['POST'])
@jwt_required()
def crawl_store():
    user = get_jwt_identity()
    payload = request.get_json(force=True)
    # Expect keys: chain (BHX/WM), storeId, optional provinceId, districtId, wardId, onlyOneProduct
    if 'storeId' not in payload or 'chain' not in payload:
        return make_response('chain and storeId required', None, 400, error='VALIDATION_ERROR')

    try:
        task = celery_crawler.send_task('crawl_tasks.crawl_store', args=[payload])
        # wait for result (optional)
        timeout = 60 if payload.get('onlyOneProduct') else 300
        result = task.get(timeout=timeout)
        return make_response('crawl completed', result, 200, requestedBy=user)
    except celery_crawler.exceptions.TimeoutError:
        return make_response('crawl timeout', None, 504, error='TIMEOUT')
    except Exception as e:
        return make_response('crawl error', None, 500, error=str(e))
