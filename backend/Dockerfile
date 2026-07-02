# Backend Dockerfile
FROM python:3.13-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ && \
    rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制后端代码（已包含 pipeline/ 目录）
COPY . .

# 创建数据目录
RUN mkdir -p /app/data/uploads /app/data/sessions /app/data/reports

# 设置 pipeline 目录环境变量
ENV PIPELINE_DIR=/app/pipeline

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
