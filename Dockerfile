FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    INSTANCE_PATH=/data/instance UPLOAD_FOLDER=/data/uploads MAIL_FOLDER=/data/mail
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --create-home --uid 10001 xelo \
    && mkdir -p /data/instance /data/uploads /data/mail \
    && chown -R xelo:xelo /data
COPY --chown=xelo:xelo . .
USER xelo
EXPOSE 8000
CMD ["python", "-m", "app"]
