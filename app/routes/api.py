from flask import Blueprint, request, jsonify, session, current_app
from app.services.db_service import DBService
from datetime import datetime

api_bp = Blueprint('api', __name__)

@api_bp.route('/notifications', methods=['GET'])
def get_notifications():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Login required'}), 403

    backend = current_app.config['DB_BACKEND']
    if backend == 'sqlite':
        from models import Notification
        notifs = Notification.query.filter_by(user_id=session['user_id']).order_by(Notification.created_at.desc()).all()
        return jsonify([{
            'id': n.id,
            'title': n.title,
            'message': n.message,
            'category': n.category,
            'is_read': n.is_read,
            'created_at': str(n.created_at)
        } for n in notifs])
    else:
        from app import mongo
        notifs = list(mongo.db.notifications.find({'user_id': str(session['user_id'])}).sort('created_at', -1))
        return jsonify([{
            'id': str(n['_id']),
            'title': n.get('title'),
            'message': n.get('message'),
            'category': n.get('category'),
            'is_read': n.get('is_read', False),
            'created_at': str(n.get('created_at'))
        } for n in notifs])

@api_bp.route('/notifications/unread-count', methods=['GET'])
def unread_notification_count():
    if 'user_id' not in session:
        return jsonify({'count': 0})

    backend = current_app.config['DB_BACKEND']
    if backend == 'sqlite':
        from models import Notification
        count = Notification.query.filter_by(user_id=session['user_id'], is_read=False).count()
    else:
        from app import mongo
        count = mongo.db.notifications.count_documents({'user_id': str(session['user_id']), 'is_read': False})
    return jsonify({'count': count})

# ... other API routes would go here (recommend, book, etc.) ...
