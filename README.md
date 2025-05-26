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
- Popüler not başlıkları analizi

## Servisler

Proje aşağıdaki servisleri kullanır:

1. **Django Web Uygulaması** - Ana web uygulaması
2. **PostgreSQL** - Veritabanı 
3. **Redis** - Önbellekleme ve mesaj kuyrukları için
4. **Celery** - Arka plan görevleri için
5. **Ollama (Gemma:2b LLM)** - Yapay zeka hizmetleri için
6. **Spark** - Büyük ölçekli not analizi için

## Kurulum ve Çalıştırma

### İlk Kurulum

```bash
# Projeyi klonlayın
git clone <repository_url>
cd <repository_directory>

# Docker Compose ile servisleri ilk kez başlatın (--build parametresi ile imajları oluşturur)
docker-compose up --build -d

# Migrasyonları oluşturun ve uygulayın
docker-compose exec web python manage.py makemigrations
docker-compose exec web python manage.py migrate

# LLM modelini yükleyin
docker-compose exec ollama ollama pull gemma:2b
```

### Sonraki Kullanımlar

```bash
# Servisleri başlatın
docker-compose up -d

# Servisleri durdurun
docker-compose down

# Servisleri yeniden başlatın
docker-compose restart
```

## Yapay Zeka Özellikleri

1. **LMS Asistanı (Chatbot)**: Öğrenciler, derslerle ilgili soruları sorabilir ve anında yanıt alabilirler. Bu özellik Ollama üzerinde çalışan Gemma:2b LLM'i kullanır.

2. **Not Zenginleştirme**: Her not için, LLM modelini kullanarak:
   - Notların otomatik özetini oluşturma
   - Çalışma soruları oluşturma

3. **Not Analizi**: Spark kullanarak:
   - En popüler not başlıklarını tespit etme
   - Kişiselleştirilmiş not önerileri sunma

## Veri Yedekleme ve Geri Yükleme

Proje, verilerin güvenli bir şekilde yedeklenmesi ve geri yüklenmesi için scriptler içerir:

```bash
# Yedekleme
./backup_docker_volumes.sh

# Geri yükleme
./restore_docker_volumes.sh docker_backups_YYYYMMDD_HHMMSS.tar.gz
```

## Kullanılan Teknolojiler

- **Django 5.2** - Web framework
- **PostgreSQL** - Veritabanı
- **Redis** - Önbellekleme ve mesaj kuyrukları
- **Celery** - Asenkron görev işleme
- **Ollama** - Yerel LLM çalıştırma platformu
- **Gemma:2b** - LLM modeli
- **Spark** - Büyük veri işleme
- **Docker & Docker Compose** - Konteynerizasyon ve orkestrasyon

## Geliştirme

Yerel geliştirme ortamında çalıştırmak için:

```bash
# PostgreSQL, Redis, Celery, Ollama ve Spark servislerini Docker ile çalıştırın
docker-compose up -d db redis ollama spark spark-worker

# Virtualenv oluşturun ve gerekli paketleri yükleyin
python -m venv myenv
source myenv/bin/activate  # Linux/Mac
myenv\Scripts\activate  # Windows
pip install -r requirements.txt

# Django uygulamasını çalıştırın
python manage.py runserver
``` 