from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('login/', views.loginPage, name='login'),
    path('logout/', views.logoutUser, name='logout'),
    path('register/', views.registerPage, name='register'),

    path('', views.dashboard, name='dashboard'),
    path('dashboard/', views.dashboard, name='dashboard'),

    path('forum/', views.home, name='home'),
    path('room/<str:pk>/', views.room, name='room'),
    path('profile/<str:pk>', views.userProfile, name='user-profile'),

    path('create-room/', views.createRoom, name='create-room'),
    path('update-room/<str:pk>/', views.updateRoom, name='update-room'),
    path('delete-room/<str:pk>/', views.deleteRoom, name='delete-room'),
    path('delete-message/<str:pk>/', views.deleteMessage, name='delete-message'),

    path('create_lesson/', views.create_lesson, name='create_lesson'),
    path('lesson/<int:lesson_id>/', views.lesson_detail, name='lesson_detail'),
    path('lesson/<int:lesson_id>/week/<int:week_number>/', views.week_detail, name='week_detail'),
    path('create_note/', views.create_note, name='create_note'),
    path('create_note/note', views.create_note, name='note'),
    path('notes/', views.notes_list_view, name='notes_list_view'),
    path('note/<int:note_id>/', views.note_detail_view, name='note_detail'),
    path('lesson/<int:lesson_id>/week/<int:week_number>/upload-pdf/', views.upload_pdf_view, name='upload_pdf'),
    path('pdf/<int:pdf_id>/', views.view_pdf, name='view_pdf'),
    path('pdf/<int:pdf_id>/delete/', views.delete_pdf, name='delete_pdf'),
    path('lessons/', views.lessons_list, name='lessons_list'),
    path('lesson/<int:lesson_id>/edit/', views.edit_lesson, name='edit_lesson'),
    path('lesson/<int:lesson_id>/delete/', views.delete_lesson, name='delete_lesson'),
    path('note/<int:note_id>/edit/', views.edit_note, name='edit_note'),
    path('note/<int:note_id>/delete/', views.delete_note, name='delete_note'),
    path('calendar_view/', views.calendar_view, name='calendar_view'),
    path('calendar/add/', views.add_event, name='add_event'),
    path('calendar/get_events/', views.get_events, name='get_events'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


