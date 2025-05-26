from celery import shared_task
from .models import ChatMessage, Note, Lesson, Week
import time
import requests
import json
from django.conf import settings
from ollama import Client


ollama_client = Client(host=settings.OLLAMA_BASE_URL)

@shared_task
def process_chat_message(chat_id):
    """
    Sohbet mesajını LLM ile işleyip yanıt oluşturan Celery görevi
    """
    try:
        chat = ChatMessage.objects.get(id=chat_id)
        
        
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
            
            return True
            
        except Exception as e:
            print(f"Error during LLM API request: {e}")
            chat.response = "I'm sorry, I cannot respond right now. Please try again later."
            chat.save()
            return False
            
    except Exception as e:
        print(f"Error processing chat message: {e}")
        return False

@shared_task
def generate_ai_note(lesson_id, week_number, user_id, title=None, description=None):
    try:
        from django.contrib.auth.models import User
        
        
        lesson = Lesson.objects.get(id=lesson_id)
        week = Week.objects.filter(lesson_id=lesson_id, week_number=week_number).first()
        user = User.objects.get(id=user_id)
        
        
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
            response = ollama_client.generate(
                model=settings.OLLAMA_MODEL,
                prompt=prompt,
                system="You are an academic note-taking assistant. Your task is to create comprehensive, well-structured notes about educational topics. Focus on providing accurate, detailed information in a Wikipedia-style format.",
                stream=False
            )
            
            
            note = Note.objects.create(
                lesson=lesson,
                week=week,
                title=title,
                note=response['response'],
                user=user
            )
            
            print(f"Note successfully created: ID={note.id}, Title={note.title}")
            return note.id
            
        except Exception as e:
            print(f"Error generating note content: {e}")
            return None
        
    except Exception as e:
        print(f"Error creating AI note: {e}")
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