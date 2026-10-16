FROM python:3.14-slim

WORKDIR /app
RUN useradd --create-home --uid 1000 app \
  && apt-get update \
  && apt-get install -y --no-install-recommends libpq5 \
  && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN chmod 755 entrypoint-api.sh && chown -R app:app /app
USER app
EXPOSE 8000
ENTRYPOINT ["./entrypoint-api.sh"]
