# Używamy lekkiego Pythona
FROM python:3.13-slim

# Ustawiamy katalog roboczy
WORKDIR /app

# Kopiujemy pliki
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Port dla Flask
EXPOSE 8080

# Uruchamiamy przez Gunicorn
CMD ["gunicorn", "-b", "0.0.0.0:8080", "app:app"]
