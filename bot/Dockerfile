FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["sh", "-c", "python check_token.py && if [ \"${TELEGRAM_BOT_TOKEN}\" = \"put_token_here\" ] || [ -z \"${TELEGRAM_BOT_TOKEN}\" ]; then exit 0; fi; python -m app.main"]
