# Django Öğrenme Yönetim Sistemi (LMS)

Bu proje, öğrencilerin derslerini, notlarını ve etkinliklerini yönetebilecekleri kapsamlı bir öğrenme yönetim sistemidir. Sistem ayrıca forum, takvim ve yapay zeka destekli chatbot ve not zenginleştirme özellikleri içerir.

## Özellikler

- Ders yönetimi (oluşturma, düzenleme, silme)
- Haftalık ders yapısı
- Not oluşturma ve yönetme
- PDF yükleme ve görüntüleme
- Takvim ve etkinlik yönetimi
- Forum ve tartışma odaları
- Yapay zeka destekli chatbot
- Not zenginleştirme (özet ve çalışma soruları)

## Servisler

Proje aşağıdaki servisleri kullanır:

1. **Django Web Uygulaması** - Ana web uygulaması
2. **PostgreSQL** - Veritabanı 
3. **Redis** - Önbellekleme ve mesaj kuyrukları için
4. **Celery** - Arka plan görevleri için
5. **Ollama (Mistral LLM)** - Yapay zeka hizmetleri için

## Kurulum ve Çalıştırma

Projeyi Docker Compose ile çalıştırmak için:

```bash
# Projeyi klonlayın
git clone <repository_url>
cd <repository_directory>

# Docker Compose ile servisleri başlatın
docker-compose up -d

# İlk kez çalıştırıyorsanız, migrasyonları uygulamak için aşağıdaki komutu çalıştırın
docker-compose exec web python manage.py migrate

# LLM modelini yüklemek için (ilk çalıştırmada gereklidir)
docker-compose exec ollama ollama pull mistral
```

## Yapay Zeka Özellikleri

1. **LMS Asistanı (Chatbot)**: Öğrenciler, derslerle ilgili soruları sorabilir ve anında yanıt alabilirler. Bu özellik Ollama üzerinde çalışan Mistral LLM'i kullanır.

2. **Not Zenginleştirme**: Her not için, LLM modelini kullanarak:
   - Notların otomatik özetini oluşturma
   - Çalışma soruları oluşturma

## Kullanılan Teknolojiler

- **Django 5.2** - Web framework
- **PostgreSQL** - Veritabanı
- **Redis** - Önbellekleme ve mesaj kuyrukları
- **Celery** - Asenkron görev işleme
- **Ollama** - Yerel LLM çalıştırma platformu
- **Mistral 7B** - LLM modeli
- **Docker & Docker Compose** - Konteynerizasyon ve orkestrasyonun

## Geliştirme

Yerel geliştirme ortamında çalıştırmak için:

```bash
# PostgreSQL, Redis, Celery ve Ollama servislerini Docker ile çalıştırın
docker-compose up -d db redis celery ollama

# Virtualenv oluşturun ve gerekli paketleri yükleyin
python -m venv myenv
source myenv/bin/activate  # Linux/Mac
myenv\Scripts\activate  # Windows
pip install -r requirements.txt

# Django uygulamasını çalıştırın
python manage.py runserver
``` 