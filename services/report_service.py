from database.mongodb import MongoDBConnection
from datetime import datetime, timedelta

db = MongoDBConnection.get_primary_db()

def dashboard_summary():
    now = datetime.utcnow()

    users_total = db.users.count_documents({})

    since_7d = now - timedelta(days=7)
    users_new_7d = db.users.count_documents({'created_at': {'$gte': since_7d}})

    dishes_total = db.dishes.count_documents({})

    ingredient_total = db.ingredients.count_documents({})

    since_24h = now - timedelta(hours=24)
    crawls_failed = db.crawls.count_documents({
        'status': 'queue',
        'updated_at': {'$lte': since_24h}
    })

    return {
        'users_total': users_total,
        'users_new_7d': users_new_7d,
        'dishes_total': dishes_total,
        'ingredients_total': ingredient_total,
        'crawls_failed': crawls_failed
    }


def users_trend(weeks: int):
    now = datetime.utcnow()
    result = []
    for i in range(weeks):
        end = now - timedelta(weeks=i)
        start = end - timedelta(weeks=1)
        count = db.users.count_documents({
            'created_at': {'$gte': start, '$lt': end}
        })
        result.append({
            'week_start': start.strftime('%Y-%m-%d'),
            'count': count
        })
    return list(reversed(result))


def recent_activity(activity_type: str, limit: int):
    if activity_type == 'dishes':
        cursor = db.dishes.find().sort('_id', -1).limit(limit)
    else:  
        cursor = db.crawling_tasks.find().sort('_id', -1).limit(limit)

    items = []
    for doc in cursor:
        doc['_id'] = str(doc['_id'])
        items.append(doc)
    return items
