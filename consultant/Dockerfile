# consultant/Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt # 构建依赖库
COPY . .
CMD ["python", "-m", "api.main"]