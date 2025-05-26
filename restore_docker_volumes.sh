#!/bin/bash

if [ -z "$1" ]; then
    echo "Lütfen yedek dosyasının adını belirtin"
    echo "Kullanım: ./restore_docker_volumes.sh docker_backups_YYYYMMDD_HHMMSS.tar.gz"
    exit 1
fi

BACKUP_FILE=$1
RESTORE_DIR="restore_$(date +%Y%m%d_%H%M%S)"

# Yedek dosyasını aç
echo "Yedek dosyası açılıyor..."
mkdir -p $RESTORE_DIR
tar -xzf $BACKUP_FILE -C $RESTORE_DIR

# PostgreSQL veritabanını geri yükle
echo "PostgreSQL veritabanı geri yükleniyor..."
docker compose exec -T db psql -U postgres -d postgres < $RESTORE_DIR/postgres_backup.sql

# Redis verilerini geri yükle
echo "Redis verileri geri yükleniyor..."
docker cp $RESTORE_DIR/redis_data/. $(docker compose ps -q redis):/data

# Spark verilerini geri yükle
echo "Spark verileri geri yükleniyor..."
docker cp $RESTORE_DIR/spark_data/. $(docker compose ps -q spark):/bitnami/spark

# Ollama verilerini geri yükle
echo "Ollama verileri geri yükleniyor..."
docker cp $RESTORE_DIR/ollama_data/. $(docker compose ps -q ollama):/root/.ollama

# Geçici dizini temizle
rm -rf $RESTORE_DIR

echo "Geri yükleme tamamlandı!" 