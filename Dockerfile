# Uma única imagem para os três papéis; o docker-compose escolhe o script.
FROM python:3.14-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    MPLCONFIGDIR=/tmp/matplotlib
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY *.py ./
