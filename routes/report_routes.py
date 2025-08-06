from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from middleware.admin_middleware import admin_required
from services.report_service import (
    dashboard_summary, users_trend, recent_activity
)


report_bp = Blueprint('report', __name__)

@report_bp.route('/summary', methods=['GET'])
@jwt_required()
@admin_required
def get_dashboard_summary():
    """
    Trả về tổng quan key metrics:
      - users_total
      - users_new_7d
      - dishes_total
      - ingredients_low_stock
      - crawls_failed_24h
    """
    try:
        summary = dashboard_summary()
        return jsonify(summary), 200
    except Exception as e:
        return jsonify({'message': f'Error fetching dashboard summary: {str(e)}'}), 500
    
@report_bp.route('/users/trend', methods=['GET'])
@jwt_required()
@admin_required
def get_users_trend():
    """
    Trả về số user đăng ký theo tuần trong N tuần:
      query params: weeks (int, default=4)
    """
    try:
        weeks = int(request.args.get('weeks', 4))
        trend = users_trend(weeks)
        return jsonify(trend), 200
    except ValueError:
        return jsonify({'message': 'Invalid parameter: weeks must be integer'}), 400
    except Exception as e:
        return jsonify({'message': f'Error fetching user trend: {str(e)}'}), 500
    
@report_bp.route('/recent', methods=['GET'])
@jwt_required()
@admin_required
def get_recent_activity():
    """
    Trả về mục Recent Activity:
      - type: 'dishes' hoặc 'crawls'
      - limit: số phần tử (mặc định=5)
    """
    try:
        activity_type = request.args.get('type')
        limit = int(request.args.get('limit', 5))
        if activity_type not in ('dishes', 'crawls'):
            return jsonify({'message': "Invalid type. Use 'dishes' or 'crawls'"}), 400

        recent = recent_activity(activity_type, limit)
        return jsonify(recent), 200
    except ValueError:
        return jsonify({'message': 'Invalid parameter: limit must be integer'}), 400
    except Exception as e:
        return jsonify({'message': f'Error fetching recent activity: {str(e)}'}), 500

