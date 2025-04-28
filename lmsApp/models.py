from django.db import models
from django.conf import settings
from django.contrib.auth.models import User

# Create your models here.

class Lesson(models.Model):
    name = models.CharField(max_length=200)
    field = models.CharField(max_length=200)  # çap öğrencileri için opsiyonel
    teacher = models.CharField(max_length=200)  # optional
    user = models.ForeignKey(User, on_delete=models.CASCADE, default=1)

    def __str__(self):
        return self.name


class Week(models.Model):
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE)
    week_number = models.IntegerField()
    user = models.ForeignKey(User, on_delete=models.CASCADE, default=1)

    def _str_(self):
        return f"Week {self.week_number} of {self.lesson.name}"


class Note(models.Model):
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE)
    week = models.ForeignKey(Week, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    note = models.TextField()
    user = models.ForeignKey(User, on_delete=models.CASCADE, default=1)

    def _str_(self):
        return f"{self.title} ({self.lesson.name} - Week {self.week.week_number})"


class WeekPDF(models.Model):
    week = models.ForeignKey(Week, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    pdf = models.FileField(upload_to='pdfs/')
    user = models.ForeignKey(User, on_delete=models.CASCADE, default=1)


    def __str__(self):
        return f"PDF for {self.week}: {self.title}"

class Event(models.Model):
    title = models.CharField(max_length=200, default='Default Title')
    date = models.DateField()
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return self.title

class Topic(models.Model):
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name


class Room(models.Model):
    host = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    topic = models.ForeignKey('Topic', on_delete=models.SET_NULL, null=True)
    name = models.CharField(max_length=200)
    description = models.TextField(null=True, blank=True)
    participants = models.ManyToManyField(User, related_name='participants', blank=True)
    updated = models.DateTimeField(auto_now=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-updated', '-created']

    def __str__(self):
        return self.name


class Message(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    body = models.TextField()
    updated = models.DateTimeField(auto_now=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-updated', '-created']

    def __str__(self):
        return self.body[0:50]


