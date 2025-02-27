# Użyj oficjalnego obrazu Pythona jako podstawy
FROM python:3.9-slim

# Ustaw katalog roboczy w kontenerze
WORKDIR /app

# Skopiuj plik requirements.txt do kontenera
COPY requirements.txt .

# Zainstaluj zależności
RUN pip install --no-cache-dir -r requirements.txt

# Skopiuj resztę plików projektu do kontenera
COPY . .

# Uruchom aplikację
CMD ["python", "main.py"]