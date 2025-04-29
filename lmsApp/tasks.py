from celery import shared_task
from .llm_utils import get_llm_response
from .models import ChatMessage, Note, Lesson, Week
import time
import requests
import json
from django.conf import settings

@shared_task
def process_chat_message(chat_id):
    """
    Sohbet mesajını LLM ile işleyip yanıt oluşturan Celery görevi
    """
    try:
        chat = ChatMessage.objects.get(id=chat_id)
        
        # Daha kapsamlı ve sınırlayıcı sistem promptu
        system_prompt = """Sen bir öğrenci asistanısın. Adın LMS Asistanı.
        Görevin öğrencilere eğitim konularında yardımcı olmaktır.
        
        Yanıtların şu özelliklere sahip olmalıdır:
        1. Kısa ve öz (3-4 cümle)
        2. Doğru Türkçe ile yazılmış
        3. Konuyla doğrudan ilgili
        4. Tutarlı ve anlaşılır
        
        Eğer sorulan konu hakkında bilgin yoksa veya soru anlaşılmazsa, kibarca açıklama iste.
        Dini, siyasi veya tartışmalı konulara girmeden, sadece akademik ve eğitsel yanıtlar ver.
        Gerçek hayattaki bir asistanı taklit et, felsefik veya derin cevaplar verme.
        """
        
        # Daha basit bir prompt, maksimum 100 token alacak şekilde
        prompt = chat.message.strip()
        if len(prompt) > 500:
            prompt = prompt[:500]  # Çok uzun girdileri sınırla
        
        # Doğrudan Ollama API'sine istek
        url = f"{settings.OLLAMA_BASE_URL}/api/generate"
        
        payload = {
            "model": settings.OLLAMA_MODEL,
            "prompt": prompt,
            "system": system_prompt,
            "stream": False,
            "max_tokens": 200  # Yanıt boyutunu sınırla
        }
        
        try:
            # Kısa bir bekleme süresi
            time.sleep(0.5)
            
            # Timeout süresini uzatma
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            
            # Yanıtı kaydet
            result = response.json()
            response_text = result.get("response", "Yanıt alınamadı. Lütfen daha sonra tekrar deneyin.")
            
            # Gereksiz metinleri temizle
            response_text = response_text.replace("LMS Asistanı:", "").strip()
            
            chat.response = response_text
            chat.save()
            
            return True
        except Exception as e:
            print(f"LLM API isteği sırasında hata: {e}")
            chat.response = "Üzgünüm, şu anda yanıt veremiyorum. Lütfen daha sonra tekrar deneyin."
            chat.save()
            return False
            
    except Exception as e:
        print(f"Sohbet mesajı işlenirken hata oluştu: {e}")
        return False

@shared_task
def generate_ai_note(lesson_id, week_number, user_id, title=None, description=None):
    """
    Belirtilen ders ve hafta için AI tarafından bir not oluşturur
    """
    try:
        from django.contrib.auth.models import User
        
        # Ders ve hafta bilgilerini al
        lesson = Lesson.objects.get(id=lesson_id)
        week = Week.objects.filter(lesson_id=lesson_id, week_number=week_number).first()
        user = User.objects.get(id=user_id)
        
        # Eğer hafta bulunamazsa, otomatik olarak oluştur
        if not week:
            week = Week.objects.create(
                lesson_id=lesson_id,
                week_number=week_number,
                user_id=user_id
            )
        
        # Eğer başlık verilmemişse otomatik bir başlık oluştur
        if not title:
            title = f"{lesson.name} - Hafta {week.week_number} Notları"
        
        # Geçici olarak Ollama API'sini atla ve doğrudan bir not içeriği oluştur
        if description:
            note_content = f"""# {title}

## Giriş
Bu not, {lesson.name} dersinin {week.week_number}. haftası için '{description}' konusunda oluşturulmuştur.

## Ana Kavramlar
- {description} konusunun temel kavramları
- Öğrencilerin anlaması gereken önemli noktalar
- Konunun teorik temelleri

## Örnekler
1. Örnek uygulama 1
2. Örnek uygulama 2
3. Gerçek hayattan örnekler

## Özet
{description} konusu, {lesson.name} dersinin önemli bir parçasıdır ve alan için kritik öneme sahiptir.

## Önerilen Kaynaklar
- Ders kitabı: '{lesson.name} Temel Kavramlar'
- Online kaynaklar
- Ek okuma materyalleri
"""
        else:
            note_content = f"""# {title}

## Giriş
Bu not, {lesson.name} dersinin {week.week_number}. haftası için oluşturulmuştur.

## Ana Kavramlar
- Dersin temel kavramları
- Öğrencilerin anlaması gereken önemli noktalar
- Teorik temeller

## Örnekler
1. Örnek uygulama 1
2. Örnek uygulama 2
3. Gerçek hayattan örnekler

## Özet
{lesson.name} dersinin bu haftaki konuları, alanın temel prensiplerini içermektedir.

## Önerilen Kaynaklar
- Ders kitabı: '{lesson.name} Temel Kavramlar'
- Online kaynaklar
- Ek okuma materyalleri
"""

        # Yeni not oluştur
        note = Note.objects.create(
            lesson=lesson,
            week=week,
            title=title,
            note=note_content,
            user=user
        )
        
        print(f"Not başarıyla oluşturuldu: ID={note.id}, Başlık={note.title}")
        return note.id
        
    except Exception as e:
        print(f"AI notu oluşturulurken hata oluştu: {e}")
        return None

@shared_task
def daily_summarize_notes():
    """
    Günlük olarak özetlenmemiş notları özetleyen görev
    """
    # AI özeti olmayan notları al
    notes = Note.objects.filter(ai_summary__isnull=True)[:10]  # Performans için limitli
    
    for note in notes:
        try:
            prompt = f"""
            Aşağıdaki ders notunu özetle:
            
            {note.note}
            
            Lütfen sadece özet ver, diğer yorumları ekleme.
            """
            
            summary = get_llm_response(prompt)
            
            # Özeti kaydet
            note.ai_summary = summary[:500]
            note.save()
        except Exception as e:
            print(f"Not {note.id} özetlenirken hata oluştu: {e}")
            continue
    
    return True

@shared_task
def send_message_to_chatbot(message, user_id=None, chat_id=None):
    """
    AI sohbet asistanına mesaj gönderen ve yanıt alıp döndüren Celery görevi
    """
    try:
        # Sohbet mesajı yoksa yeni oluştur
        if not chat_id:
            # Yeni bir ChatMessage objesi oluştur ve kaydet
            from django.contrib.auth.models import User
            user = User.objects.get(id=user_id) if user_id else None
            
            chat = ChatMessage.objects.create(
                message=message,
                user=user
            )
            chat_id = chat.id
        else:
            chat = ChatMessage.objects.get(id=chat_id)
        
        # Daha kapsamlı ve sınırlayıcı sistem promptu
        system_prompt = """Sen bir not asistanısın. Adın Not Asistanı.
        Görevin öğrencilere not alma konusunda yardımcı olmaktır.
        
        Yanıtların şu özelliklere sahip olmalıdır:
        1. Kısa ve öz (3-4 cümle)
        2. Doğru Türkçe ile yazılmış
        3. Not alma konusuyla doğrudan ilgili
        4. Tutarlı ve anlaşılır
        
        Kullanıcı ders notu oluşturma isterse, bu konuda yardımcı ol. 
        Hangi ders ve hafta için not istediklerini sor.
        Eğer sorulan konu hakkında bilgin yoksa veya soru anlaşılmazsa, kibarca açıklama iste.
        """
        
        # Prompt hazırla
        prompt = message.strip()
        if len(prompt) > 500:
            prompt = prompt[:500]  # Çok uzun girdileri sınırla
        
        # Doğrudan Ollama API'sine istek
        url = f"{settings.OLLAMA_BASE_URL}/api/generate"
        
        payload = {
            "model": settings.OLLAMA_MODEL,
            "prompt": prompt,
            "system": system_prompt,
            "stream": False,
            "max_tokens": 200  # Yanıt boyutunu sınırla
        }
        
        try:
            # Kısa bir bekleme süresi
            time.sleep(0.5)
            
            # Timeout süresini uzatma
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            
            # Yanıtı kaydet
            result = response.json()
            response_text = result.get("response", "Yanıt alınamadı. Lütfen daha sonra tekrar deneyin.")
            
            # Gereksiz metinleri temizle
            response_text = response_text.replace("Not Asistanı:", "").strip()
            
            chat.response = response_text
            chat.save()
            
            return response_text
        except Exception as e:
            print(f"LLM API isteği sırasında hata: {e}")
            error_message = "Üzgünüm, şu anda yanıt veremiyorum. Lütfen daha sonra tekrar deneyin."
            chat.response = error_message
            chat.save()
            return error_message
            
    except Exception as e:
        print(f"Sohbet mesajı işlenirken hata oluştu: {e}")
        return "Bir hata oluştu. Lütfen daha sonra tekrar deneyin." 