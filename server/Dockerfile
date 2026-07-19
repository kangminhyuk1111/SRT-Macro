FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt requirements-server.txt ./
RUN pip install --no-cache-dir -r requirements-server.txt

COPY src ./src
COPY server ./server

# config.*.json 저장 위치 (docker-compose에서 볼륨 마운트)
ENV SRTMACRO_CONFIG_DIR=/data

EXPOSE 8000
CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8000"]
