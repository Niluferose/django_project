FROM python:3.12-slim-bookworm

WORKDIR /app

# PostgreSQL client'ı yükle
RUN apt-get update && apt-get install -y postgresql-client

COPY requirements.txt .
RUN pip3 install -r requirements.txt

COPY . .

CMD ["python3", "manage.py", "runserver", "0.0.0.0:8000"]
