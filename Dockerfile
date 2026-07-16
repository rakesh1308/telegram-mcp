FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py ./

# PaaS platforms (Zeabur, Railway, Render, Heroku, Fly.io) inject PORT.
# Our server.py detects PORT and switches from stdio to streamable-http.
ENV PORT=8080
EXPOSE 8080

CMD ["python", "server.py"]