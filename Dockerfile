FROM python:3.11-slim-bookworm

WORKDIR /app

# Java ve gerekli araçları yükle
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    default-jdk \
    procps \
    python3-distutils \
    && rm -rf /var/lib/apt/lists/*

# JAVA_HOME'u otomatik ayarla
RUN export JAVA_HOME=$(dirname $(dirname $(readlink -f $(which javac)))) && \
    echo "export JAVA_HOME=$JAVA_HOME" >> /etc/profile.d/java_home.sh && \
    echo "export PATH=\$PATH:\$JAVA_HOME/bin" >> /etc/profile.d/java_home.sh

ENV JAVA_HOME=/usr/lib/jvm/default-java
ENV PATH=$JAVA_HOME/bin:$PATH

COPY requirements.txt .
RUN pip3 install --upgrade pip setuptools wheel && \
    pip3 install -r requirements.txt

COPY . .

CMD ["python3", "manage.py", "runserver", "0.0.0.0:8000"]
