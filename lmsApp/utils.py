import redis
import json
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

# Redis bağlantısı
redis_client = redis.Redis(
    host=settings.REDIS_HOST, 
    port=settings.REDIS_PORT, 
    db=3,  # Bildirimler için ayrı DB
    decode_responses=True
)

class NotificationService:
    """Redis Pub/Sub ile real-time bildirim sistemi"""
    
    @staticmethod
    def send_notification(user_id, notification_type, message, data=None):
        """Kullanıcıya bildirim gönder"""
        notification = {
            'type': notification_type,
            'message': message,
            'data': data or {},
            'timestamp': str(timezone.now())
        }
        
        # Pub/Sub ile gönder
        channel = f"user_{user_id}_notifications"
        redis_client.publish(channel, json.dumps(notification))
        
        # Cache'te de sakla (offline kullanıcılar için)
        cache_key = f"notifications_{user_id}"
        notifications = cache.get(cache_key, [])
        notifications.append(notification)
        
        # Son 50 bildirimi sakla
        if len(notifications) > 50:
            notifications = notifications[-50:]
            
        cache.set(cache_key, notifications, 86400)  # 24 saat
    
    @staticmethod
    def get_user_notifications(user_id):
        """Kullanıcının bildirimlerini getir"""
        cache_key = f"notifications_{user_id}"
        return cache.get(cache_key, [])
    
    @staticmethod
    def mark_as_read(user_id, notification_index=None):
        """Bildirimleri okundu olarak işaretle"""
        cache_key = f"notifications_{user_id}"
        notifications = cache.get(cache_key, [])
        
        if notification_index is not None:
            if 0 <= notification_index < len(notifications):
                notifications[notification_index]['read'] = True
        else:
            # Tümünü okundu işaretle
            for notification in notifications:
                notification['read'] = True
                
        cache.set(cache_key, notifications, 86400)

class CacheService:
    """Akıllı cache yönetimi"""
    
    @staticmethod
    def get_user_lessons_cache_key(user_id):
        """Kullanıcı dersleri için cache key"""
        return f"user_lessons_{user_id}"
    
    @staticmethod
    def get_lesson_notes_cache_key(lesson_id, user_id):
        """Ders notları için cache key"""
        return f"lesson_notes_{lesson_id}_{user_id}"
    
    @staticmethod
    def get_popular_notes_cache_key(lesson_id):
        """Popüler notlar için cache key"""
        return f"popular_notes_{lesson_id}"
    
    @staticmethod
    def invalidate_user_cache(user_id):
        """Kullanıcı cache'ini temizle"""
        patterns = [
            f"user_lessons_{user_id}",
            f"lesson_notes_*_{user_id}",
            f"notifications_{user_id}",
            f"user_notes_{user_id}",
            f"user_chat_messages_{user_id}"
        ]
        
        for pattern in patterns:
            if '*' in pattern:
                # Wildcard pattern için tüm anahtarları bul ve sil
                keys = cache.keys(pattern.replace('*', '*'))
                for key in keys:
                    cache.delete(key)
            else:
                cache.delete(pattern)
    
    @staticmethod
    def cache_lesson_data(lesson_id, user_id, data, timeout=300):
        """Ders verilerini cache'le"""
        cache_key = CacheService.get_lesson_notes_cache_key(lesson_id, user_id)
        cache.set(cache_key, data, timeout)
    
    @staticmethod
    def get_cached_lesson_data(lesson_id, user_id):
        """Cache'lenmiş ders verilerini getir"""
        cache_key = CacheService.get_lesson_notes_cache_key(lesson_id, user_id)
        return cache.get(cache_key)

class RateLimitService:
    """Rate limiting servisi"""
    
    @staticmethod
    def check_rate_limit(user_id, action, limit=10, window=3600):
        """Rate limit kontrolü (saatte X işlem)"""
        cache_key = f"rate_limit_{action}_{user_id}"
        current_count = cache.get(cache_key, 0)
        
        if current_count >= limit:
            return False, f"Saatte en fazla {limit} {action} işlemi yapabilirsiniz."
        
        # Sayacı artır
        cache.set(cache_key, current_count + 1, window)
        return True, None
    
    @staticmethod
    def get_remaining_attempts(user_id, action, limit=10):
        """Kalan deneme hakkını getir"""
        cache_key = f"rate_limit_{action}_{user_id}"
        current_count = cache.get(cache_key, 0)
        return max(0, limit - current_count)

class SessionService:
    """Gelişmiş session yönetimi"""
    
    @staticmethod
    def track_user_activity(user_id, activity_type, data=None):
        """Kullanıcı aktivitesini takip et"""
        cache_key = f"user_activity_{user_id}"
        activities = cache.get(cache_key, [])
        
        activity = {
            'type': activity_type,
            'data': data or {},
            'timestamp': str(timezone.now())
        }
        
        activities.append(activity)
        
        # Son 100 aktiviteyi sakla
        if len(activities) > 100:
            activities = activities[-100:]
            
        cache.set(cache_key, activities, 86400)
    
    @staticmethod
    def get_user_activity(user_id):
        """Kullanıcı aktivitelerini getir"""
        cache_key = f"user_activity_{user_id}"
        return cache.get(cache_key, [])
    
    @staticmethod
    def get_online_users():
        """Online kullanıcıları getir"""
        return cache.get('online_users', [])
    
    @staticmethod
    def set_user_online(user_id):
        """Kullanıcıyı online olarak işaretle"""
        online_users = cache.get('online_users', [])
        if user_id not in online_users:
            online_users.append(user_id)
        cache.set('online_users', online_users, 300)  # 5 dakika
        
        # Kullanıcının son görülme zamanı
        cache.set(f"last_seen_{user_id}", timezone.now(), 86400)

from django.utils import timezone 