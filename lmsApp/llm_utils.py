import requests
import json
from django.conf import settings
from celery import shared_task

def get_llm_response(prompt, system_prompt=None):
    """
    Ollama API'sine istek gönderip LLM yanıtını alır
    """
    url = f"{settings.OLLAMA_BASE_URL}/api/generate"
    
    payload = {
        "model": settings.OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False
    }
    
    # Eğer sistem promptu varsa ekle
    if system_prompt:
        payload["system"] = system_prompt
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()  # HTTP hatalarını kontrol et
        
        return response.json()["response"]
    except Exception as e:
        print(f"LLM yanıtı alınırken hata oluştu: {e}")
        return "Üzgünüm, şu anda yanıt veremiyorum. Lütfen daha sonra tekrar deneyin."

@shared_task
def generate_note_summary(note_id):
    """
    Bir not için özet oluşturan Celery görevi
    """
    from .models import Note  # Dairesel içe aktarmaları önlemek için burada import

    try:
        note = Note.objects.get(id=note_id)
        
        prompt = f"""
        Aşağıdaki ders notunu özetle:
        
        {note.note}
        
        Lütfen sadece özet ver, diğer yorumları ekleme.
        """
        
        summary = get_llm_response(prompt)
        
        # Özeti kaydet (kısa tutmak için ilk 500 karakter)
        note.ai_summary = summary[:500]
        note.save()
        
        return True
    except Exception as e:
        print(f"Not özeti oluşturulurken hata oluştu: {e}")
        return False

@shared_task
def generate_study_questions(note_id):
    """
    Bir not için çalışma soruları oluşturan Celery görevi
    """
    from .models import Note  # Dairesel içe aktarmaları önlemek için burada import
    
    try:
        note = Note.objects.get(id=note_id)
        
        prompt = f"""
        Aşağıdaki ders notu için 3 çalışma sorusu oluştur:
        
        {note.note}
        
        Lütfen sadece soruları ver, diğer yorumları ekleme.
        """
        
        questions = get_llm_response(prompt)
        
        # Soruları kaydet
        note.ai_questions = questions
        note.save()
        
        return True
    except Exception as e:
        print(f"Çalışma soruları oluşturulurken hata oluştu: {e}")
        return False 