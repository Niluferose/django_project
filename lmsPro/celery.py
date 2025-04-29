import os
from celery import Celery

# Django ayarlarını Celery için ayarla
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lmsPro.settings')

app = Celery('lmsPro')

# 'CELERY' ile başlayan ayarları Django settings'ten al
app.config_from_object('django.conf:settings', namespace='CELERY')

# Görevleri Django uygulamalarından otomatik olarak yükle
app.autodiscover_tasks()

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}') 