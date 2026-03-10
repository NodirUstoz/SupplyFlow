version: "3.9"

services:
  db:
    image: postgres:15-alpine
    restart: unless-stopped
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-supplyflow}
      POSTGRES_USER: ${POSTGRES_USER:-supplyflow}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-supplyflow}
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-supplyflow}"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    restart: unless-stopped
    command: >
      sh -c "python manage.py migrate --noinput &&
             python manage.py collectstatic --noinput &&
             gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 4 --timeout 120"
    volumes:
      - ./backend:/app
      - static_volume:/app/staticfiles
      - media_volume:/app/media
    environment:
      DJANGO_SETTINGS_MODULE: ${DJANGO_SETTINGS_MODULE:-config.settings.development}
      DJANGO_SECRET_KEY: ${DJANGO_SECRET_KEY:-change-me-in-production}
      DJANGO_DEBUG: ${DJANGO_DEBUG:-True}
      DATABASE_URL: postgres://${POSTGRES_USER:-supplyflow}:${POSTGRES_PASSWORD:-supplyflow}@db:5432/${POSTGRES_DB:-supplyflow}
      REDIS_URL: redis://redis:6379/0
      ALLOWED_HOSTS: ${ALLOWED_HOSTS:-localhost,127.0.0.1,backend}
      CORS_ALLOWED_ORIGINS: ${CORS_ALLOWED_ORIGINS:-http://localhost,http://localhost:3000}
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy

  celery_worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    restart: unless-stopped
    command: celery -A config.celery worker -l info --concurrency=4
    volumes:
      - ./backend:/app
    environment:
      DJANGO_SETTINGS_MODULE: ${DJANGO_SETTINGS_MODULE:-config.settings.development}
      DJANGO_SECRET_KEY: ${DJANGO_SECRET_KEY:-change-me-in-production}
      DATABASE_URL: postgres://${POSTGRES_USER:-supplyflow}:${POSTGRES_PASSWORD:-supplyflow}@db:5432/${POSTGRES_DB:-supplyflow}
      REDIS_URL: redis://redis:6379/0
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy

  celery_beat:
    build:
      context: ./backend
      dockerfile: Dockerfile
    restart: unless-stopped
    command: celery -A config.celery beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
    volumes:
      - ./backend:/app
    environment:
      DJANGO_SETTINGS_MODULE: ${DJANGO_SETTINGS_MODULE:-config.settings.development}
      DJANGO_SECRET_KEY: ${DJANGO_SECRET_KEY:-change-me-in-production}
      DATABASE_URL: postgres://${POSTGRES_USER:-supplyflow}:${POSTGRES_PASSWORD:-supplyflow}@db:5432/${POSTGRES_DB:-supplyflow}
      REDIS_URL: redis://redis:6379/0
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    restart: unless-stopped
    volumes:
      - ./frontend:/app
      - /app/node_modules
    ports:
      - "3000:3000"
    environment:
      REACT_APP_API_URL: ${REACT_APP_API_URL:-http://localhost/api}
    depends_on:
      - backend

  nginx:
    image: nginx:1.25-alpine
    restart: unless-stopped
    ports:
      - "80:80"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/conf.d/default.conf:ro
      - static_volume:/app/staticfiles:ro
      - media_volume:/app/media:ro
    depends_on:
      - backend
      - frontend

volumes:
  postgres_data:
  redis_data:
  static_volume:
  media_volume:
