FROM node:24-alpine AS frontend
WORKDIR /build
COPY frontend/package*.json frontend/.npmrc ./
RUN npm ci --ignore-scripts
COPY frontend/ ./
RUN npm run build

FROM python:3.14-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY backend/requirements.lock.txt ./requirements.lock.txt
RUN pip install --no-cache-dir -r requirements.lock.txt && useradd --uid 10001 --create-home finops
COPY backend/ ./backend/
COPY database/alembic.ini ./database/alembic.ini
COPY database/migrations/ ./database/migrations/
COPY --from=frontend /build/dist ./frontend/dist
RUN chown -R finops:finops /app
USER finops
EXPOSE 8000
CMD ["sh", "-c", "if [ \"${PUBLIC_DEMO:-false}\" = \"true\" ]; then python -m backend.app.cli migrate; else python -m backend.app.cli init; fi && exec uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
