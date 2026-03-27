FROM python:3.9-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    software-properties-common \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
COPY app/ ./app/
COPY analysis/ ./analysis/

RUN pip3 install -r requirements.txt

EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/health

ENTRYPOINT ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8501"]