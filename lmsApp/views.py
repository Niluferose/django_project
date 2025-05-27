from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.forms import UserCreationForm
from .models import Room, Topic, Message, Lesson, Note, Week, WeekPDF, Event, ChatMessage, PopularNoteTitle
from .forms import RoomForm

from lmsApp.forms import LessonForm, NotesForm, PDFUploadForm, EventForm, EditNoteForm, ChatForm
from django.urls import reverse
from django.db import transaction
from django.http import FileResponse
from django.http import JsonResponse
from .tasks import process_chat_message, generate_ai_note, send_message_to_chatbot
import json
from .analysis.note_analysis import get_top_notes, analyze_notes
from django.conf import settings
from ollama import Client

# Redis Cache imports
from django.core.cache import cache
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_cookie
import hashlib

# Utils imports
from .utils import NotificationService, CacheService, RateLimitService, SessionService

ollama_client = Client(host=settings.OLLAMA_BASE_URL)


@login_required(login_url='login')
def dashboard(request):
    # Kullanıcıyı online olarak işaretle
    SessionService.set_user_online(request.user.id)
    
    # Aktivite takibi
    SessionService.track_user_activity(request.user.id, 'dashboard_visit')
    
    # Cache'den dersleri getirmeye çalış
    cache_key = CacheService.get_user_lessons_cache_key(request.user.id)
    lessons = cache.get(cache_key)
    
    if lessons is None:
        # Cache'de yoksa veritabanından getir
        lessons = list(Lesson.objects.filter(user=request.user).values(
            'id', 'name', 'field', 'teacher'
        ))
        # 5 dakika cache'le
        cache.set(cache_key, lessons, 300)
    
    # Bildirimleri getir
    notifications = NotificationService.get_user_notifications(request.user.id)
    unread_count = len([n for n in notifications if not n.get('read', False)])
    
    # Online kullanıcı sayısı
    online_users = SessionService.get_online_users()
    
    context = {
        'lessons': lessons,
        'notifications': notifications[:5],  # Son 5 bildirim
        'unread_count': unread_count,
        'online_users_count': len(online_users)
    }
    
    print(lessons)  
    return render(request, 'lmsApp/dashboard.html', context)

@login_required(login_url='login')
def create_lesson(request):
    if request.method == 'POST':
        form = LessonForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                name = form.cleaned_data['name']
                field = form.cleaned_data['field']
                teacher = form.cleaned_data['teacher']
                lesson = Lesson.objects.create(name=name, field=field, teacher=teacher, user=request.user)

                for week_number in range(1, 15):
                    Week.objects.create(lesson=lesson, week_number=week_number, user=request.user)

                # İlgili cache'leri temizle
                lessons_cache_key = CacheService.get_user_lessons_cache_key(request.user.id)
                cache.delete(lessons_cache_key)
                
                # Dashboard cache'ini de temizle
                dashboard_cache_key = f"user_lessons_{request.user.id}"
                cache.delete(dashboard_cache_key)

                # Yeni ders oluşturulduğunda bildirim gönder
                NotificationService.send_notification(
                    request.user.id,
                    'lesson_created',
                    f'🎓 Yeni ders "{name}" başarıyla oluşturuldu! 14 haftalık plan hazır.',
                    {'lesson_id': lesson.id, 'lesson_name': name}
                )

                url = reverse('lesson_detail', kwargs={'lesson_id': lesson.id})
                return redirect(url)
    else:
        form = LessonForm()
    return render(request, 'lmsApp/create_lesson.html', context={'form': form})


@login_required(login_url='login')
def create_note(request):
    if not Lesson.objects.filter(user=request.user).exists():
        return redirect('create_lesson') 

    if request.method == 'POST':
        form = NotesForm(request.POST)
        form.fields['lesson'].queryset = Lesson.objects.filter(user=request.user)
        if form.is_valid():
            with transaction.atomic():
                lesson = form.cleaned_data['lesson']
                week_number = form.cleaned_data['week_number']
                title = form.cleaned_data['title']
                note_text = form.cleaned_data['note']

                
                week = Week.objects.get(lesson=lesson, week_number=week_number, user=request.user)
                note = Note.objects.create(lesson=lesson, week=week, title=title, note=note_text, user=request.user)
                
                # Cache'leri temizle
                lesson_cache_key = CacheService.get_lesson_notes_cache_key(lesson.id, request.user.id)
                cache.delete(lesson_cache_key)
                
                # Yeni not oluşturulduğunda bildirim gönder
                NotificationService.send_notification(
                    request.user.id,
                    'note_created',
                    f'📝 "{title}" başlıklı notunuz {lesson.name} dersine eklendi!',
                    {'note_id': note.id, 'lesson_name': lesson.name, 'week': week_number}
                )
                
                url = reverse('week_detail', kwargs={'lesson_id': lesson.id, 'week_number': week.week_number})
                return redirect(url)
    else:
        form = NotesForm()
        form.fields['lesson'].queryset = Lesson.objects.filter(user=request.user)

    return render(request, 'lmsApp/create_note.html', {'form': form})


@login_required(login_url='login')
def lessons_list(request):
    # Cache kullanmadan direkt veritabanından getir (template uyumluluğu için)
    lessons = Lesson.objects.filter(user=request.user).order_by('-created')
    return render(request, 'lmsApp/lesson.html', {'lessons': lessons})
@login_required(login_url='login')
def lesson_detail(request, lesson_id):
    lesson = Lesson.objects.get(id=lesson_id, user=request.user)
    weeks = Week.objects.filter(lesson=lesson, user=request.user).order_by('week_number')
    return render(request, 'lmsApp/lesson_detail.html', {'lesson': lesson, 'weeks': weeks})

@login_required(login_url='login')
def edit_lesson(request, lesson_id):
    lesson = Lesson.objects.get(id=lesson_id, user=request.user)
    if request.method == 'POST':
        form = LessonForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                lesson.name = form.cleaned_data['name']
                lesson.field = form.cleaned_data['field']
                lesson.teacher = form.cleaned_data['teacher']
                lesson.save()
                return redirect('lessons_list')
    else:
        form = LessonForm(initial={'name': lesson.name, 'field': lesson.field, 'teacher': lesson.teacher})
    return render(request, 'lmsApp/edit_lesson.html', {'form': form})



@login_required(login_url='login')
def delete_lesson(request, lesson_id):
    lesson = Lesson.objects.get(id=lesson_id, user=request.user)
    if request.method == 'POST':
        lesson_name = lesson.name
        
        with transaction.atomic():
            # Dersi sil
            lesson.delete()
            
            # İlgili cache'leri temizle
            lessons_cache_key = CacheService.get_user_lessons_cache_key(request.user.id)
            cache.delete(lessons_cache_key)
            
            # Dashboard cache'ini de temizle
            dashboard_cache_key = f"user_lessons_{request.user.id}"
            cache.delete(dashboard_cache_key)
            
            # Ders notları cache'lerini temizle
            lesson_cache_key = CacheService.get_lesson_notes_cache_key(lesson_id, request.user.id)
            cache.delete(lesson_cache_key)
            
            # Ders silme bildirimi gönder
            NotificationService.send_notification(
                request.user.id,
                'lesson_deleted',
                f'🗑️ "{lesson_name}" dersi ve tüm içeriği başarıyla silindi.',
                {'lesson_name': lesson_name}
            )
            
            messages.success(request, f'"{lesson_name}" dersi başarıyla silindi.')
            return redirect('lessons_list')
    return render(request, 'lmsApp/delete_lesson.html', {'lesson': lesson})


@login_required(login_url='login')
def upload_pdf_view(request, lesson_id, week_number):
    lesson = Lesson.objects.get(id=lesson_id, user=request.user)
    week = Week.objects.get(lesson=lesson, week_number=week_number, user=request.user)

    if request.method == 'POST':
        form = PDFUploadForm(request.POST, request.FILES)
        if form.is_valid():
            week_pdf = form.save(commit=False)
            week_pdf.week = week
            week_pdf.user = request.user
            week_pdf.save()
            
            # PDF yüklendiğinde bildirim gönder
            NotificationService.send_notification(
                request.user.id,
                'pdf_uploaded',
                f'📄 {lesson.name} dersi {week_number}. haftaya PDF başarıyla yüklendi!',
                {'pdf_id': week_pdf.id, 'lesson_name': lesson.name, 'week': week_number}
            )
            
            return redirect(reverse('week_detail', kwargs={'lesson_id': lesson.id, 'week_number': week.week_number}))
    else:
        form = PDFUploadForm()

    return render(request, 'lmsApp/upload_pdf.html', {'lesson': lesson, 'week': week, 'form': form})

@login_required(login_url='login')
def week_detail(request, lesson_id, week_number):
    lesson = Lesson.objects.get(id=lesson_id, user=request.user)
    week = Week.objects.get(lesson=lesson, week_number=week_number, user=request.user)
    notes = week.note_set.filter(user=request.user)
    pdfs = WeekPDF.objects.filter(week=week, user=request.user)
    
    
    ai_note_generated = False
    if request.method == 'POST' and 'generate_ai_note' in request.POST:
        title = request.POST.get('note_title', f"{lesson.name} - Hafta {week.week_number} AI Notları")
        description = request.POST.get('description')
        
        if not description:
            messages.error(request, 'Not oluşturmak için konu açıklaması gereklidir.')
            return redirect('week_detail', lesson_id=lesson_id, week_number=week_number)
        
        
        task = generate_ai_note.delay(lesson_id, week_number, request.user.id, title, description)
        messages.success(request, 'AI tarafından not oluşturuluyor. Bu işlem biraz zaman alabilir.')
        ai_note_generated = True
    
    return render(request, 'lmsApp/week_detail.html', {
        'lesson': lesson, 
        'week': week, 
        'notes': notes, 
        'pdfs': pdfs,
        'ai_note_generated': ai_note_generated
    })

@login_required(login_url='login')
def view_pdf(request, pdf_id):
    pdf = WeekPDF.objects.get(id=pdf_id, week__lesson__user=request.user)
    return FileResponse(pdf.pdf.open(), content_type='application/pdf')

@login_required(login_url='login')
def delete_pdf(request, pdf_id):
    pdf = WeekPDF.objects.get(id=pdf_id, week__lesson__user=request.user)
    if request.method == 'POST':
        pdf.delete()
        return redirect(reverse('week_detail', kwargs={'lesson_id': pdf.week.lesson.id, 'week_number': pdf.week.week_number}))
    return render(request, 'lmsApp/delete_pdf.html', {'pdf': pdf})

@login_required(login_url='login')
def note_detail_view(request, note_id):
    note = Note.objects.get(id=note_id, user=request.user)
    
    
    if request.method == 'POST':
        action = request.POST.get('action')
    
    return render(request, 'lmsApp/note_detail.html', {'note': note})


@login_required(login_url='login')
def notes_list_view(request):
    # Cache kullanmadan direkt veritabanından getir (template uyumluluğu için)
    notes = Note.objects.filter(user=request.user).select_related('lesson', 'week').order_by('-created')
    
    # Dersleri cache'den getir
    lessons_cache_key = CacheService.get_user_lessons_cache_key(request.user.id)
    all_lessons = cache.get(lessons_cache_key)
    
    if all_lessons is None:
        all_lessons = Lesson.objects.filter(user=request.user)
        cache.set(lessons_cache_key, list(all_lessons.values('id', 'name', 'field', 'teacher')), 300)
    else:
        # Cache'den gelen dictionary'leri Lesson object'lerine dönüştür
        all_lessons = Lesson.objects.filter(user=request.user)
    
    return render(request, 'lmsApp/note_list.html', {'notes': notes, 'all_lessons': all_lessons})


@login_required(login_url='login')
def edit_note(request, note_id):
    note = Note.objects.get(id=note_id, user=request.user)
    if request.method == 'POST':
        form = EditNoteForm(request.POST, instance=note)  
        if form.is_valid():
            form.save()
            return redirect('note_detail', note_id=note.id)  
    else:
        form = EditNoteForm(instance=note)  
    return render(request, 'lmsApp/edit_note.html', {'form': form})


@login_required(login_url='login')
def delete_note(request, note_id):
    note = Note.objects.get(id=note_id, user=request.user)
    if request.method == 'POST':
        lesson_id = note.lesson.id
        week_number = note.week.week_number
        note_title = note.title
        
        # Notu sil
        note.delete()
        
        # İlgili cache'leri temizle
        lesson_cache_key = CacheService.get_lesson_notes_cache_key(lesson_id, request.user.id)
        cache.delete(lesson_cache_key)
        
        # Kullanıcı dersleri cache'ini temizle
        lessons_cache_key = CacheService.get_user_lessons_cache_key(request.user.id)
        cache.delete(lessons_cache_key)
        
        # Not silme bildirimi gönder
        NotificationService.send_notification(
            request.user.id,
            'note_deleted',
            f'🗑️ "{note_title}" başlıklı not başarıyla silindi.',
            {'lesson_id': lesson_id, 'week': week_number}
        )
        
        messages.success(request, f'"{note_title}" başlıklı not başarıyla silindi.')
        return redirect('notes_list_view')
    return render(request, 'lmsApp/delete_note.html', {'note': note})

@login_required(login_url='login')
def calendar_view(request):
    return render(request, 'lmsApp/calendar.html')

@login_required(login_url='login')
def get_events(request):
    events = Event.objects.filter(user=request.user)
    event_list = [{'title': event.title, 'date': event.date.isoformat()} for event in events]
    return JsonResponse(event_list, safe=False)

@login_required(login_url='login')
def add_event(request):
    if request.method == 'POST':
        form = EventForm(request.POST)
        if form.is_valid():
            event = form.save(commit=False)
            event.user = request.user
            event.save()
            
            # Yeni etkinlik eklendiğinde bildirim gönder
            NotificationService.send_notification(
                request.user.id,
                'event_created',
                f'📅 "{event.title}" etkinliği {event.date.strftime("%d.%m.%Y")} tarihine eklendi!',
                {'event_id': event.id, 'event_title': event.title, 'date': str(event.date)}
            )
            
            messages.success(request, 'Event added successfully!')
            return redirect('calendar_view')
        else:
            messages.error(request, 'Invalid data. Please check the form.')
    else:
        form = EventForm()
    return render(request, 'lmsApp/add_event.html', {'form': form})

@login_required(login_url='login')
def chatbot_view(request):
    # Rate limiting kontrolü
    can_proceed, error_msg = RateLimitService.check_rate_limit(
        request.user.id, 'chatbot', limit=20, window=3600  # Saatte 20 mesaj
    )
    
    # Cache'den mesajları getir
    cache_key = f"user_chat_messages_{request.user.id}"
    user_messages = cache.get(cache_key)
    
    if user_messages is None:
        user_messages = list(ChatMessage.objects.filter(user=request.user)
                           .order_by('-created')[:10]
                           .values('id', 'message', 'response', 'created'))
        cache.set(cache_key, user_messages, 300)  # 5 dakika cache
    
    if request.method == 'POST':
        if not can_proceed:
            messages.error(request, error_msg)
            return redirect('chatbot')
            
        form = ChatForm(request.POST)
        if form.is_valid():
            message = form.cleaned_data['message']
            
            # Aktivite takibi
            SessionService.track_user_activity(
                request.user.id, 
                'chatbot_message', 
                {'message_length': len(message)}
            )
            
            chat = ChatMessage.objects.create(
                user=request.user,
                message=message,
                response="İşleniyor... Lütfen bekleyin."
            )
            
            # Cache'i temizle
            cache.delete(cache_key)
            
            # Bildirim gönder
            NotificationService.send_notification(
                request.user.id,
                'chatbot_processing',
                'AI asistanınız mesajınızı işliyor...',
                {'chat_id': chat.id}
            )
            
            process_chat_message.delay(chat.id)
            
            return redirect('chatbot')
    else:
        form = ChatForm()
    
    # Kalan deneme hakkı
    remaining_attempts = RateLimitService.get_remaining_attempts(
        request.user.id, 'chatbot', limit=20
    )
    
    return render(request, 'lmsApp/chatbot.html', {
        'form': form,
        'messages': user_messages,
        'remaining_attempts': remaining_attempts
    })

@login_required(login_url='login')
def delete_chat_message(request, message_id):
    """Belirli bir sohbet mesajını siler"""
    try:
        message = ChatMessage.objects.get(id=message_id, user=request.user)
        if request.method == 'POST':
            message.delete()
            messages.success(request, 'Mesaj başarıyla silindi.')
            return redirect('chatbot')
        return render(request, 'lmsApp/delete_chat_message.html', {'message': message})
    except ChatMessage.DoesNotExist:
        messages.error(request, 'Mesaj bulunamadı.')
        return redirect('chatbot')

@login_required(login_url='login')
def clear_chat(request):
    """Kullanıcının tüm sohbet mesajlarını siler"""
    if request.method == 'POST':
        ChatMessage.objects.filter(user=request.user).delete()
        messages.success(request, 'Tüm sohbet mesajları silindi.')
    return redirect('chatbot')

@login_required(login_url='login')
def new_chat(request):
    """Yeni bir sohbet başlatır (eski mesajları silmeden)"""
    return redirect('chatbot')



def loginPage(request):
    page = 'login'
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        username = request.POST.get('username').lower()
        password = request.POST.get('password')

        try:
            user = User.objects.get(username=username)
        except:
            messages.error(request, 'User does not exist.')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, 'Username OR password does not exist.')

    context = {'page': page}
    return render(request, 'lmsApp/login_register.html', context)


def logoutUser(request):
    logout(request)
    return redirect('dashboard')


def registerPage(request):
    form = UserCreationForm()

    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.username = user.username.lower()
            user.save()
            login(request, user)
            return redirect('home')
        else:
            messages.error(request, 'An error occurred during registration.')

    return render(request, 'lmsApp/login_register.html', {'form': form})


def loginPage2(request):
    return render(request, 'lmsApp/login_register_old.html')


def dashboardPage(request):
    return render(request, 'lmsApp/dashboard.html')


def home(request):
    q = request.GET.get('q') if request.GET.get('q') != None else ''
    rooms = Room.objects.filter(topic__name__icontains=q)

    topics = Topic.objects.all()
    room_count = rooms.count()
    room_messages = Message.objects.filter(Q(room__topic__name__icontains=q))

    context = {'rooms': rooms, 'topics': topics, 'room_count': room_count, 'room_messages': room_messages}
    return render(request, 'lmsApp/home.html', context)


def room(request, pk):
    room = Room.objects.get(id=pk)
    room_messages = room.message_set.all()
    participants = room.participants.all()

    if request.method == 'POST':
        message = Message.objects.create(
            user=request.user,
            room=room,
            body=request.POST.get('body'),
        )
        room.participants.add(request.user)
        return redirect('room', pk=room.id)

    context = {'room': room, 'room_messages': room_messages, 'participants': participants}
    return render(request, 'lmsApp/room.html', context)


def userProfile(request, pk):
    user = User.objects.get(id=pk)
    rooms = user.room_set.all()
    room_messages = user.message_set.all()
    topics = Topic.objects.all()
    context = {'user': user, 'rooms': rooms, 'room_messages': room_messages, 'topics': topics}
    return render(request, 'lmsApp/profile.html', context)


@login_required(login_url='login')
def createRoom(request):
    form = RoomForm()

    if request.method == 'POST':
        form = RoomForm(request.POST)
        if form.is_valid():
            room = form.save(commit=False)
            room.host = request.user
            room.save()
            return redirect('home')

    context = {'form': form}
    return render(request, 'lmsApp/room_form.html', context)


@login_required(login_url='login')
def updateRoom(request, pk):
    room = Room.objects.get(id=pk)
    form = RoomForm(instance=room)

    if request.user != room.host:
        return HttpResponse('You are not allowed here!')

    if request.method == 'POST':
        form = RoomForm(request.POST, instance=room)
        if form.is_valid():
            form.save()
            return redirect('home')

    context = {'form': form}
    return render(request, 'lmsApp/room_form.html', context)


@login_required(login_url='login')
def deleteRoom(request, pk):
    room = Room.objects.get(id=pk)

    if request.user != room.host:
        return HttpResponse('You are not allowed here!')

    if request.method == 'POST':
        room.delete()
        return redirect('home')

    return render(request, 'lmsApp/delete.html', {'obj': room})


@login_required(login_url='login')
def deleteMessage(request, pk):
    message = Message.objects.get(id=pk)

    if request.user != message.user:
        return HttpResponse('You are not allowed here!')

    if request.method == 'POST':
        message.delete()
        return redirect('home')

    return render(request, 'lmsApp/delete.html', {'obj': message})

@login_required
def note_list(request):
    current_user = request.user
    notes = Note.objects.filter(user=current_user)
    all_lessons = Lesson.objects.all()  
    return render(request, 'lmsApp/note_list.html', {
        'notes': notes,
        'all_lessons': all_lessons
    })

@login_required
def ai_generate_note(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            lesson_id = data.get('lesson_id')
            week_number = data.get('week')
            description = data.get('description')

            print(f"Gelen veriler - lesson_id: {lesson_id}, week: {week_number}, description: {description}")

            if not lesson_id or not week_number:
                return JsonResponse({
                    'success': False,
                    'error': 'Ders ve hafta bilgisi gereklidir.'
                })

            lesson = get_object_or_404(Lesson, id=lesson_id)
            week_number = int(week_number)
            print(f"Ders bulundu: {lesson.name}, Hafta: {week_number}")

            
            if not description:
                try:
                    print(f"Not analizi başlıyor... Ders ID: {lesson_id}")
                    
                    analyze_notes(lesson_id=lesson_id)
                    print("Not analizi tamamlandı, öneriler getiriliyor...")
                    
                    
                    suggestions = get_top_notes(5, request.user.id, lesson_id)
                    print(f"Öneriler: {suggestions}")
                    
                    return JsonResponse({
                        'success': True,
                        'needs_suggestion': True,
                        'suggestions': suggestions if suggestions else [],
                        'message': f'{lesson.name} dersinin {week_number}. haftası için not oluşturacağım. Aşağıdaki önerilerden birini seçebilir veya kendi konunuzu yazabilirsiniz:'
                    })
                except Exception as e:
                    print(f"Analiz sırasında hata: {str(e)}")
                    import traceback
                    print(f"Hata detayı: {traceback.format_exc()}")
                    return JsonResponse({
                        'success': True,
                        'needs_suggestion': True,
                        'suggestions': [],
                        'message': f'{lesson.name} dersinin {week_number}. haftası için not oluşturacağım. Lütfen bu haftanın konusunu veya oluşturmak istediğiniz notun içeriğini kısaca açıklayın.'
                    })

            
            
            title = description[:50]  
            
            week = Week.objects.filter(lesson_id=lesson_id, week_number=week_number).first()
            if not week:
                week = Week.objects.create(
                    lesson_id=lesson_id,
                    week_number=week_number,
                    user_id=request.user.id
                )
            
            prompt = f"""Write a comprehensive academic note about {description} in the context of {lesson.name}. Focus on answering these questions:
            1. What is {description} in {lesson.name}? (Definition and basic explanation)
            2. How is {description} used in {lesson.name}? (Main applications and use cases)
            3. What are the key concepts and principles related to {description} in {lesson.name}?
            4. What are the practical examples and applications in {lesson.name}?
            5. References and resources for further study in {lesson.name}
            
            Format the note in a clear, structured way with headings and bullet points where appropriate.
            Make sure the content is specifically relevant to {lesson.name} and its field of study.
            """
            
            try:
                response = ollama_client.generate(
                    model=settings.OLLAMA_MODEL,
                    prompt=prompt,
                    system="You are an academic note-taking assistant. Your task is to create comprehensive, well-structured notes about educational topics. Focus on providing accurate, detailed information in a Wikipedia-style format.",
                    stream=False
                )
                
                
                note_content = response.get('response', '')
                if not note_content:
                    note_content = str(response)
                
                note = Note.objects.create(
                    lesson=lesson,
                    week=week,
                    title=title,
                    note=note_content,
                    user=request.user
                )
                
                
                suggestions = get_top_notes(5, request.user.id, lesson_id)
                
                
                analyze_notes(lesson_id=lesson_id)
                
                return JsonResponse({
                    'success': True,
                    'title': title,
                    'note_id': note.id,
                    'suggestions': suggestions
                })
                
            except Exception as e:
                print(f"Not oluşturma sırasında hata: {str(e)}")
                return JsonResponse({'success': False, 'error': f'Not oluşturulurken hata: {str(e)}'})
            
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Geçersiz JSON verisi.'})
        except Exception as e:
            print(f"Genel hata: {str(e)}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Sadece POST istekleri destekleniyor.'})


def redirect_to_dashboard(request):
    return redirect('dashboard')

def redirect_to_notes(request):
    return redirect('notes_list_view')

def redirect_to_lessons(request):
    return redirect('lessons_list')

def redirect_to_calendar(request):
    return redirect('calendar_view')

def redirect_to_forum(request):
    return redirect('home')

def redirect_to_chatbot(request):
    return redirect('chatbot')

# Bildirim API Endpoints
@login_required(login_url='login')
def get_notifications(request):
    """Kullanıcının bildirimlerini JSON olarak döndür"""
    notifications = NotificationService.get_user_notifications(request.user.id)
    return JsonResponse({
        'notifications': notifications,
        'unread_count': len([n for n in notifications if not n.get('read', False)])
    })

@login_required(login_url='login')
def mark_notification_read(request, notification_id):
    """Bildirimi okundu olarak işaretle"""
    if request.method == 'POST':
        NotificationService.mark_as_read(request.user.id, notification_id)
        return JsonResponse({'success': True})
    return JsonResponse({'success': False})

@login_required(login_url='login')
def mark_all_notifications_read(request):
    """Tüm bildirimleri okundu olarak işaretle"""
    if request.method == 'POST':
        NotificationService.mark_as_read(request.user.id)
        return JsonResponse({'success': True})
    return JsonResponse({'success': False})

@login_required(login_url='login')
def get_user_activity(request):
    """Kullanıcı aktivitelerini getir"""
    activities = SessionService.get_user_activity(request.user.id)
    return JsonResponse({'activities': activities})

@login_required(login_url='login')
def get_system_stats(request):
    """Sistem istatistiklerini getir"""
    online_users = SessionService.get_online_users()
    
    # Cache istatistikleri
    cache_stats = {
        'online_users': len(online_users),
        'total_notifications': len(NotificationService.get_user_notifications(request.user.id)),
        'user_activities': len(SessionService.get_user_activity(request.user.id))
    }
    
    return JsonResponse(cache_stats)

@login_required(login_url='login')
def clear_user_cache(request):
    """Kullanıcı cache'ini temizle"""
    if request.method == 'POST':
        CacheService.invalidate_user_cache(request.user.id)
        messages.success(request, 'Cache başarıyla temizlendi.')
        return JsonResponse({'success': True})
    return JsonResponse({'success': False})



