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

# Ollama client'ı oluştur
ollama_client = Client(host=settings.OLLAMA_BASE_URL)

# Create your views here.

# Sniffer
@login_required(login_url='login')
def dashboard(request):
    lessons = Lesson.objects.filter(user=request.user)
    print(lessons)  # Debug statement
    return render(request, 'lmsApp/dashboard.html', {'lessons': lessons})

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

                url = reverse('lesson_detail', kwargs={'lesson_id': lesson.id})
                return redirect(url)
    else:
        form = LessonForm()
    return render(request, 'lmsApp/create_lesson.html', context={'form': form})


@login_required(login_url='login')
def create_note(request):
    if not Lesson.objects.filter(user=request.user).exists():
        return redirect('create_lesson')  # create_lesson url'ine yönlendirme

    if request.method == 'POST':
        form = NotesForm(request.POST)
        form.fields['lesson'].queryset = Lesson.objects.filter(user=request.user)
        if form.is_valid():
            with transaction.atomic():
                lesson = form.cleaned_data['lesson']
                week_number = form.cleaned_data['week_number']
                title = form.cleaned_data['title']
                note_text = form.cleaned_data['note']

                # İlgili haftayı belirleyin
                week = Week.objects.get(lesson=lesson, week_number=week_number, user=request.user)
                Note.objects.create(lesson=lesson, week=week, title=title, note=note_text, user=request.user)
                url = reverse('week_detail', kwargs={'lesson_id': lesson.id, 'week_number': week.week_number})
                return redirect(url)
    else:
        form = NotesForm()
        form.fields['lesson'].queryset = Lesson.objects.filter(user=request.user)

    return render(request, 'lmsApp/create_note.html', {'form': form})


@login_required(login_url='login')
def lessons_list(request):
    lessons = Lesson.objects.filter(user=request.user)
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
        with transaction.atomic():
            lesson.delete()
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
    
    # AI notu oluşturma isteği kontrol ediliyor
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
    
    # Eğer oluşturma isteği gelirse
    if request.method == 'POST':
        action = request.POST.get('action')
    
    return render(request, 'lmsApp/note_detail.html', {'note': note})


@login_required(login_url='login')
def notes_list_view(request):
    notes = Note.objects.filter(user=request.user)
    all_lessons = Lesson.objects.filter(user=request.user)  # Kullanıcının derslerini all_lessons olarak ekle
    return render(request, 'lmsApp/note_list.html', {'notes': notes, 'all_lessons': all_lessons})


@login_required(login_url='login')
def edit_note(request, note_id):
    note = Note.objects.get(id=note_id, user=request.user)
    if request.method == 'POST':
        form = EditNoteForm(request.POST, instance=note)  # instance kullanarak sadece title ve note alanlarını düzenliyoruz
        if form.is_valid():
            form.save()
            return redirect('note_detail', note_id=note.id)  # Burada ilgili notun detay sayfasına yönlendiriyoruz
    else:
        form = EditNoteForm(instance=note)  # instance kullanarak formu dolduruyoruz
    return render(request, 'lmsApp/edit_note.html', {'form': form})


@login_required(login_url='login')
def delete_note(request, note_id):
    note = Note.objects.get(id=note_id, user=request.user)
    if request.method == 'POST':
        note.delete()
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
            messages.success(request, 'Event added successfully!')
            return redirect('calendar_view')
        else:
            messages.error(request, 'Invalid data. Please check the form.')
    else:
        form = EventForm()
    return render(request, 'lmsApp/add_event.html', {'form': form})

@login_required(login_url='login')
def chatbot_view(request):
    user_messages = ChatMessage.objects.filter(user=request.user).order_by('-created')[:10]
    
    if request.method == 'POST':
        form = ChatForm(request.POST)
        if form.is_valid():
            message = form.cleaned_data['message']
            
            # Yeni mesaj oluştur
            chat = ChatMessage.objects.create(
                user=request.user,
                message=message,
                response="İşleniyor... Lütfen bekleyin."
            )
            
            # Arka planda işleme başlat
            process_chat_message.delay(chat.id)
            
            return redirect('chatbot')
    else:
        form = ChatForm()
    
    return render(request, 'lmsApp/chatbot.html', {
        'form': form,
        'messages': user_messages
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

# Sniffer


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
    all_lessons = Lesson.objects.all()  # Burada tüm dersleri alıyoruz
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

            # Eğer açıklama yoksa, önce analiz yap ve önerileri getir
            if not description:
                try:
                    print(f"Not analizi başlıyor... Ders ID: {lesson_id}")
                    # Önce notları analiz et
                    analyze_notes(lesson_id=lesson_id)
                    print("Not analizi tamamlandı, öneriler getiriliyor...")
                    
                    # Sonra önerileri getir
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

            # Not oluşturma işlemi
            # Başlık sadece konu başlığı olsun
            title = description[:50]  # Açıklamayı başlık olarak kullan, maksimum 50 karakter
            
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
                
                # API yanıtını güvenli bir şekilde işle
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
                
                # Not ekledikten sonra öneri fonksiyonunu tekrar çağır
                suggestions = get_top_notes(5, request.user.id, lesson_id)
                
                # Not ekledikten sonra PopularNoteTitle tablosunu güncelle
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

# URL yönlendirme görünüm fonksiyonları
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



