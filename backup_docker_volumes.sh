#!/bin/bash

# Yedekleme dizini oluştur
BACKUP_DIR="docker_backups_$(date +%Y%m%d_%H%M%S)"
mkdir -p $BACKUP_DIR

# PostgreSQL volume'unu yedekle
echo "PostgreSQL volume'u yedekleniyor..."
docker compose exec -T db pg_dump -U postgres -d postgres > $BACKUP_DIR/postgres_backup.sql

# Redis volume'unu yedekle
echo "Redis volume'u yedekleniyor..."
docker compose exec redis redis-cli SAVE
docker cp $(docker compose ps -q redis):/data $BACKUP_DIR/redis_data

# Spark volume'unu yedekle
echo "Spark volume'u yedekleniyor..."
docker cp $(docker compose ps -q spark):/bitnami/spark $BACKUP_DIR/spark_data

# Ollama volume'unu yedekle
echo "Ollama volume'u yedekleniyor..."
docker cp $(docker compose ps -q ollama):/root/.ollama $BACKUP_DIR/ollama_data

# Yedekleri sıkıştır
echo "Yedekler sıkıştırılıyor..."
tar -czf $BACKUP_DIR.tar.gz $BACKUP_DIR

# Geçici dizini temizle
rm -rf $BACKUP_DIR

echo "Yedekleme tamamlandı: $BACKUP_DIR.tar.gz" 