from django.forms import ModelForm
from django import forms
from .models import Room, Lesson, WeekPDF, Event, Note


class RoomForm(ModelForm):
    class Meta:
        model = Room
        fields = '__all__'
        exclude = ['host', 'participants']


class LessonForm(forms.Form):
    name = forms.CharField(max_length=200)
    field = forms.CharField(max_length=200)
    teacher = forms.CharField(max_length=200)
    # release_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))


class NotesForm(forms.Form):
    lesson = forms.ModelChoiceField(queryset=Lesson.objects.none())
    week_number = forms.IntegerField(min_value=1, max_value=14, required=True)
    title = forms.CharField(max_length=200)
    note = forms.CharField(widget=forms.Textarea)


class EditNoteForm(forms.ModelForm):
    class Meta:
        model = Note
        fields = ['title', 'note']
class PDFUploadForm(forms.ModelForm):
    class Meta:
        model = WeekPDF
        fields = ['title', 'pdf']

class EventForm(forms.ModelForm):
    date = forms.DateField(input_formats=['%Y-%m-%d'])

    class Meta:
        model = Event
        fields = ['title', 'date']