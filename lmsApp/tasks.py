from celery import shared_task
from .models import ChatMessage, Note, Lesson, Week
import time
import requests
import json
from django.conf import settings
from ollama import Client

# Bildirim sistemi import
from .utils import NotificationService

ollama_client = Client(host=settings.OLLAMA_BASE_URL)

@shared_task
def process_chat_message(chat_id):
    """
    Sohbet mesajını LLM ile işleyip yanıt oluşturan Celery görevi
    """
    try:
        chat = ChatMessage.objects.get(id=chat_id)
        user_id = chat.user.id
        
        # İşlem başladığında bildirim gönder
        NotificationService.send_notification(
            user_id,
            'chatbot_started',
            'AI asistanınız mesajınızı işlemeye başladı...',
            {'chat_id': chat_id}
        )
        
        system_prompt = """You are a student assistant named LMS Assistant.
        Your task is to help students with educational topics.
        
        Your responses should have these characteristics:
        1. Concise (3-4 sentences)
        2. Clear and understandable
        3. Directly related to the topic
        4. Consistent and logical
        5. Include practical examples
        6. Suitable for student level
        
        If you don't know about the topic or the question is unclear, politely ask for clarification.
        Avoid religious, political, or controversial topics. Focus only on academic and educational responses.
        Act like a real assistant, avoid philosophical or deep answers.
        """
        
        prompt = chat.message.strip()[:500]
        
        try:
            time.sleep(0.5)
            
            response = ollama_client.generate(
                model=settings.OLLAMA_MODEL,
                prompt=prompt,
                system=system_prompt,
                stream=False,
                max_tokens=200,
                temperature=0.7
            )
            
            response_text = response.response.replace("LMS Assistant:", "").strip()
            chat.response = response_text
            chat.save()
            
            # Başarılı tamamlandığında bildirim gönder
            NotificationService.send_notification(
                user_id,
                'chatbot_completed',
                'AI asistanınızdan yanıt geldi! 🤖',
                {'chat_id': chat_id, 'response_preview': response_text[:50] + '...'}
            )
            
            # Cache'i temizle
            from django.core.cache import cache
            cache.delete(f"user_chat_messages_{user_id}")
            
            return True
            
        except Exception as e:
            print(f"Error during LLM API request: {e}")
            error_response = "I'm sorry, I cannot respond right now. Please try again later."
            chat.response = error_response
            chat.save()
            
            # Hata durumunda bildirim gönder
            NotificationService.send_notification(
                user_id,
                'chatbot_error',
                'AI asistanınızda bir hata oluştu. Lütfen tekrar deneyin.',
                {'chat_id': chat_id, 'error': str(e)}
            )
            
            return False
            
    except Exception as e:
        print(f"Error processing chat message: {e}")
        return False

@shared_task
def generate_ai_note(lesson_id, week_number, user_id, title=None, description=None):
    start_time = time.time()  # Başlangıç zamanı
    
    try:
        from django.contrib.auth.models import User
        
        lesson = Lesson.objects.get(id=lesson_id)
        week = Week.objects.filter(lesson_id=lesson_id, week_number=week_number).first()
        user = User.objects.get(id=user_id)
        
        # İşlem başladığında bildirim gönder
        NotificationService.send_notification(
            user_id,
            'ai_note_started',
            f'🤖 AI "{lesson.name}" dersi için not oluşturmaya başladı...',
            {'lesson_name': lesson.name, 'week': week_number}
        )
        
        if not week:
            week = Week.objects.create(
                lesson_id=lesson_id,
                week_number=week_number,
                user_id=user_id
            )
        
        if not title:
            title = f"{lesson.name} - Week {week.week_number} Notes"
        
        if not description:
            raise ValueError("Description is required to generate a note.")
            
        prompt = f"""Write a concise note about {description}. Focus on answering these three questions:
        1. What is it? (Definition and basic explanation)
        2. Where it is used? (Main applications and use cases)
        3. References for more information (Key resources to learn more)
        """
        
        try:
            ai_start_time = time.time()  # AI işlem başlangıcı
            
            response = ollama_client.generate(
                model=settings.OLLAMA_MODEL,
                prompt=prompt,
                system="You are an academic note-taking assistant. Your task is to create comprehensive, well-structured notes about educational topics. Focus on providing accurate, detailed information in a Wikipedia-style format.",
                stream=False
            )
            
            ai_end_time = time.time()  # AI işlem bitişi
            ai_duration = round(ai_end_time - ai_start_time, 2)
            
            note = Note.objects.create(
                lesson=lesson,
                week=week,
                title=title,
                note=response['response'],
                user=user
            )
            
            end_time = time.time()  # Toplam işlem bitişi
            total_duration = round(end_time - start_time, 2)
            
            # AI not oluşturulduğunda bildirim gönder (süre bilgisi ile)
            NotificationService.send_notification(
                user_id,
                'ai_note_completed',
                f'🤖 AI tarafından "{title}" notu {total_duration}s\'de oluşturuldu! (AI: {ai_duration}s)',
                {
                    'note_id': note.id, 
                    'lesson_name': lesson.name, 
                    'week': week_number,
                    'ai_duration': ai_duration,
                    'total_duration': total_duration
                }
            )
            
            print(f"Note successfully created: ID={note.id}, Title={note.title}")
            print(f"⏱️ Timing - AI: {ai_duration}s, Total: {total_duration}s")
            return note.id
            
        except Exception as e:
            error_time = time.time()
            error_duration = round(error_time - start_time, 2)
            
            # Hata durumunda bildirim gönder
            NotificationService.send_notification(
                user_id,
                'ai_note_error',
                f'❌ AI not oluşturma {error_duration}s sonra başarısız oldu.',
                {'error': str(e), 'duration': error_duration}
            )
            
            print(f"Error generating note content: {e}")
            return None
        
    except Exception as e:
        error_time = time.time()
        error_duration = round(error_time - start_time, 2)
        print(f"Error creating AI note: {e} (Duration: {error_duration}s)")
        return None

@shared_task
def send_message_to_chatbot(message, user_id=None, chat_id=None):
    """
    Celery task that sends a message to the AI chat assistant and returns the response
    """
    try:
        if not chat_id:
            from django.contrib.auth.models import User
            user = User.objects.get(id=user_id) if user_id else None
            
            chat = ChatMessage.objects.create(
                message=message,
                user=user
            )
            chat_id = chat.id
        else:
            chat = ChatMessage.objects.get(id=chat_id)
        
        
        system_prompt = """You are a note-taking assistant named Note Assistant.
        Your task is to help students with taking notes.
        
        Your responses should have these characteristics:
        1. Concise (3-4 sentences)
        2. Clear and understandable
        3. Directly related to note-taking
        4. Consistent and logical
        5. Include practical examples
        6. Suitable for student level
        
        If the user wants to create lecture notes, help them with that.
        Ask which course and week they want notes for.
        If you don't know about the topic or the question is unclear, politely ask for clarification.
        """
        
        
        prompt = message.strip()[:500]
        
        try:
            
            time.sleep(0.5)
            
            
            response = ollama_client.generate(
                model=settings.OLLAMA_MODEL,
                prompt=prompt,
                system=system_prompt,
                stream=False,
                max_tokens=200,
                temperature=0.7
            )
            
            
            chat.response = response.response.strip()
            chat.save()
            
            return chat.response
            
        except Exception as e:
            error_msg = "I'm sorry, I cannot respond right now. Please try again later."
            chat.response = error_msg
            chat.save()
            return error_msg
            
    except Exception as e:
        print(f"Error processing chatbot message: {e}")
        return "An error occurred. Please try again later." 