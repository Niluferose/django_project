from django.core.management.base import BaseCommand
from lmsApp.analysis.note_analysis import analyze_notes

class Command(BaseCommand):
    help = 'Notları analiz eder ve en çok not alınan konuları gösterir'

    def handle(self, *args, **options):
        self.stdout.write('Not analizi başlıyor...')
        analyze_notes()
        self.stdout.write(self.style.SUCCESS('Analiz tamamlandı! Sonuçlar note_analysis.png dosyasında.')) 