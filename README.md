# 🚀 Synchronizacja Librus z Google Tasks i Discord

Projekt umożliwia automatyczną synchronizację zadań z Librusa do Google Tasks.
Dodatkowo, po każdej udanej synchronizacji, jest wysyłany na Discorda raport, a w przypadku błędu — szczegóły problemu.

---

## 📋 Funkcje
- **Synchronizacja zadań i integracja z Google Tasks**:
  - Pobieranie zadań domowych.
  - Pobieranie sprawdzianów, kartkówek.
  - Dodawanie do wybranej listy w Google Tasks.
- **Powiadomienia na Discord**:
  - Wiadomości o sukcesie (zielony embed).
  - Wiadomości o błędach (czerwony embed).

---

## 🛠 Wymagania
- Python 3.8+
- Konto Librus.
- Konto Google z dostępem do Google Tasks.
- Webhook Discord.

---

## 🔧 Konfiguracja

1. Utwórz plik `.env`

```plaintext
LIBRUS_LOGIN=twój_login_librus
LIBRUS_PASSWORD=twoje_hasło_librus
GOOGLE_TOKEN_PATH=ścieżka/do/token.json
GOOGLE_CREDENTIALS_PATH=ścieżka/do/credentials.json
DISCORD_WEBHOOK_URL=twój_url_webhooka_discord
```
2. Google API

    - Przejdź do Google Cloud Console.

    - Utwórz nowy projekt.

    - Włącz API Google Tasks.

    - Pobierz plik credentials.json i umieść go w lokalizacji wskazanej w GOOGLE_CREDENTIALS_PATH.

3. Discord Webhook

    - Przejdź do ustawień kanału Discord.

    - Utwórz nowy webhook i skopiuj jego URL.

    - Wklej URL do zmiennej DISCORD_WEBHOOK_URL w pliku .env.

🖥 **Uruchomienie bez Dockera**
  - pip install -r requirements.txt
  - python main.py

🐳 **Uruchomienie z Dockerem**
  - docker build -t librus-sync .
  - docker run --env-file .env librus-sync
