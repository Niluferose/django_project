from pyspark.sql import SparkSession
from pyspark.sql.functions import col
from django.db import connection
import pandas as pd
import matplotlib.pyplot as plt
from lmsApp.models import PopularNoteTitle, Note, Lesson

def get_top_notes(limit=5, user_id=None, lesson_id=None):
    """
    Seçilen derste, kullanıcının daha önce not almadığı en popüler başlıkları getirir.
    """
    lesson_name = Lesson.objects.get(id=lesson_id).name
    # Kullanıcının o derste aldığı başlıklar
    user_titles = set(
        Note.objects.filter(user_id=user_id, lesson_id=lesson_id).values_list('title', flat=True)
    )
    # Popüler başlıklardan, kullanıcının almadıklarını getir
    popular_titles = PopularNoteTitle.objects.filter(lesson_name=lesson_name).order_by('-count')
    results = [
        {'title': p.title}
        for p in popular_titles
        if p.title not in user_titles
    ][:limit]
    print("get_top_notes params:", lesson_id, user_id, limit)
    print("get_top_notes results:", results)
    return results

def analyze_notes(lesson_id=None):
    """
    Notları analiz eder ve en çok not alınan konuları gösterir.
    Eğer lesson_id verilmişse, sadece o dersin notlarını analiz eder.
    Verilmemişse, tüm derslerin notlarını analiz eder.
    """
    # Önce PopularNoteTitle tablosunu temizle
    if lesson_id:
        # Sadece belirli dersin verilerini temizle
        lesson = Lesson.objects.get(id=lesson_id)
        PopularNoteTitle.objects.filter(lesson_name=lesson.name).delete()
        print(f"{lesson.name} için PopularNoteTitle tablosu temizlendi.")
    else:
        # Tüm verileri temizle
        PopularNoteTitle.objects.all().delete()
        print("PopularNoteTitle tablosu tamamen temizlendi.")

    if lesson_id:
        # Sadece belirli bir dersin notlarını analiz et
        lesson = Lesson.objects.get(id=lesson_id)
        lesson_names = [lesson.name]
    else:
        # Tüm benzersiz ders isimlerini bul
        lesson_names = Lesson.objects.values_list('name', flat=True).distinct()

    for lesson_name in lesson_names:
        print(f"Analiz başlıyor: {lesson_name}")
        # O isme sahip tüm derslerin notlarını çek
        with connection.cursor() as cursor:
            cursor.execute("""
                WITH note_counts AS (
                    SELECT 
                        l.name as lesson_name,
                        n.title as note_title,
                        COUNT(DISTINCT n.id) as note_count
                    FROM "lmsApp_note" n
                    JOIN "lmsApp_lesson" l ON n.lesson_id = l.id
                    JOIN "auth_user" u ON n.user_id = u.id
                    WHERE u.is_active = true
                    AND l.name = %s
                    GROUP BY l.name, n.title
                )
                SELECT 
                    lesson_name,
                    note_title,
                    note_count
                FROM note_counts
                ORDER BY note_count DESC
            """, [lesson_name])
            results = cursor.fetchall()

        if not results:
            print(f"{lesson_name} için hiç sonuç bulunamadı.")
            continue

        # Pandas DataFrame'e dönüştür
        df = pd.DataFrame(results, columns=['lesson_name', 'note_title', 'note_count'])
        print(f"\n{lesson_name} için not sayıları:")
        print(df[['note_title', 'note_count']].to_string(index=False))

        # PopularNoteTitle tablosuna kaydet
        for _, row in df.iterrows():
            popular_title, created = PopularNoteTitle.objects.update_or_create(
                lesson_name=lesson_name,
                title=row['note_title'],
                defaults={'count': row['note_count']}
            )
            print(f"PopularNoteTitle güncellendi: {popular_title.title}, count: {popular_title.count}")
        print(f"{lesson_name} için popüler başlıklar kaydedildi.")

    # Spark oturumu oluştur
    spark = SparkSession.builder \
        .appName("NoteAnalysis") \
        .master("spark://spark:7077") \
        .config("spark.driver.host", "web") \
        .config("spark.driver.bindAddress", "0.0.0.0") \
        .config("spark.executor.memory", "1g") \
        .config("spark.driver.memory", "1g") \
        .getOrCreate()

    # Spark DataFrame'e dönüştür
    spark_df = spark.createDataFrame(df)

    # En çok not alınan konuları bul
    print("\nEn çok not alınan konular (ilk 10):")
    spark_df.orderBy(col("note_count").desc()).show(10, truncate=False)

    # Görselleştirme
    plt.figure(figsize=(12, 6))
    df_top = df.nlargest(10, 'note_count')
    plt.bar(df_top['note_title'], df_top['note_count'])
    plt.xticks(rotation=45, ha='right')
    plt.title('En Çok Not Alınan 10 Konu')
    plt.xlabel('Konu Başlığı')
    plt.ylabel('Not Sayısı')
    plt.tight_layout()
    plt.savefig('/app/note_analysis.png')
    print("Grafik kaydedildi: /app/note_analysis.png")

    # Spark oturumunu kapat
    spark.stop()

if __name__ == "__main__":
    analyze_notes()
