from django.contrib.auth.models import User
from lmsApp.models import Lesson, Week, Note

# Ders ve kullanıcıyı bul
lesson = Lesson.objects.get(id=111)  # esin kullanıcısı için Cloud Computing dersi ID'si
user = User.objects.get(username='esin')

# Haftalık notlar
week_notes = {
    1: {
        'Cloud Computing Temelleri': '''Bulut bilişim, internet üzerinden sunulan bilgi işlem kaynakları ve hizmetleridir.

Temel Özellikler:
1. Ölçeklenebilirlik
   - Dinamik kaynak ayırma
   - Otomatik ölçeklendirme
   - Yük dengeleme

2. Esneklik
   - İhtiyaca göre kaynak kullanımı
   - Ödeme modeli
   - Hizmet çeşitliliği

3. Güvenilirlik
   - Yüksek erişilebilirlik
   - Veri yedekleme
   - Felaket kurtarma''',
        'Bulut Hizmet Modelleri': '''Bulut bilişim üç temel hizmet modeli sunar.

Hizmet Modelleri:
1. IaaS (Infrastructure as a Service)
   - Sanal makineler
   - Depolama
   - Ağ altyapısı

2. PaaS (Platform as a Service)
   - Geliştirme ortamı
   - Veritabanı yönetimi
   - Uygulama barındırma

3. SaaS (Software as a Service)
   - Hazır uygulamalar
   - Web tabanlı erişim
   - Otomatik güncellemeler'''
    },
    2: {
        'Docker Temelleri': '''Docker, uygulamaların konteynerler içinde çalışmasını sağlayan bir platformdur.

Ana Bileşenler:
1. Docker Engine
   - Konteyner yaşam döngüsü
   - İmaj yönetimi
   - Ağ ve depolama

2. Docker Images
   - Uygulama paketleme
   - Katmanlı yapı
   - Yeniden kullanım

3. Docker Containers
   - İzole ortamlar
   - Kaynak kontrolü
   - Ağ yapılandırması''',
        'Docker Komutları': '''Docker ile çalışırken kullanılan temel komutlar:

İmaj İşlemleri:
1. docker pull: İmaj indirme
2. docker build: İmaj oluşturma
3. docker images: İmaj listeleme

Konteyner İşlemleri:
1. docker run: Konteyner başlatma
2. docker ps: Konteyner listeleme
3. docker stop: Konteyner durdurma

Sistem İşlemleri:
1. docker system prune: Temizlik
2. docker network: Ağ yönetimi
3. docker volume: Veri yönetimi'''
    },
    9: {
        'Cloud Security': '''Bulut güvenliği, veri ve kaynakların korunması için çok katmanlı bir yaklaşım gerektirir.

Güvenlik Katmanları:
1. Network Security
   - VPC yapılandırması
   - Güvenlik grupları
   - Network ACL'ler

2. Data Security
   - Veri şifreleme
   - Anahtar yönetimi
   - Veri sınıflandırma

3. Identity Security
   - Çok faktörlü kimlik doğrulama
   - Rol tabanlı erişim
   - Denetim kayıtları''',
        'Compliance ve Governance': '''Bulut uyumluluk ve yönetişim, standartlara uygunluğu sağlar.

Standartlar:
1. ISO 27001
   - Risk yönetimi
   - Güvenlik kontrolleri
   - Süreç yönetimi

2. GDPR
   - Veri koruma
   - Kullanıcı hakları
   - Raporlama gereksinimleri

3. HIPAA
   - Sağlık verisi güvenliği
   - Gizlilik kuralları
   - Güvenlik önlemleri'''
    }
}

# Her hafta için notları oluştur
for week_num, notes in week_notes.items():
    week = Week.objects.get(lesson=lesson, week_number=week_num, user=user)
    for topic, content in notes.items():
        Note.objects.create(
            lesson=lesson,
            week=week,
            title=f'{topic}',
            note=content,
            user=user
        )

print('Notlar başarıyla oluşturuldu!') 