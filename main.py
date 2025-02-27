import os
import requests
import traceback
from datetime import datetime, timedelta
from typing import List, Optional
from dotenv import load_dotenv
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from librus_apix.client import new_client, Client
from librus_apix.schedule import get_schedule
from librus_apix.homework import get_homework, homework_detail, Homework
from tenacity import retry, stop_after_attempt, wait_exponential

# Funkcja do formatowania logów
def log_message(message: str):
    current_time = datetime.now().strftime("[%H:%M:%S] ")
    print(f"{current_time}{message}")

# Constants
SCOPES = ['https://www.googleapis.com/auth/tasks']
TASK_LIST_NAME = "Wydarzenia Librus"
TEST_KEYWORDS = ["sprawdzian", "kartkówka"]


class GoogleTasksManager:
    def __init__(self):
        self.service = self._get_google_tasks_service()
        self.task_list_id = self._get_or_create_task_list()

    def _get_google_tasks_service(self) -> any:
        """Initialize and return Google Tasks service with proper authentication."""
        creds = None
        token_path = os.getenv('GOOGLE_TOKEN_PATH')
        credentials_path = os.getenv('GOOGLE_CREDENTIALS_PATH')

        if not token_path or not credentials_path:
            raise ValueError("Missing GOOGLE_TOKEN_PATH or GOOGLE_CREDENTIALS_PATH in .env")

        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)

        if not creds or not creds.valid:
            creds = self._refresh_or_get_new_credentials(creds, credentials_path, token_path)

        return build('tasks', 'v1', credentials=creds)

    def _refresh_or_get_new_credentials(self, creds: Optional[Credentials], credentials_path: str, token_path: str) -> Credentials:
        """Refresh existing credentials or get new ones."""
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                log_message("Token został odświeżony automatycznie.")
            except Exception as e:
                log_message(f"Błąd podczas odświeżania tokenu: {str(e)}")
                log_message("Usuwam stary token i proszę o ponowne logowanie.")
                os.remove(token_path)
                creds = None

        if not creds or not creds.valid:
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_path,
                SCOPES,
                redirect_uri='urn:ietf:wg:oauth:2.0:oob'
            )
            auth_url, _ = flow.authorization_url(prompt='consent')
            print(f"Otwórz ten link w przeglądarce i zaloguj się: {auth_url}")
            print("Po zalogowaniu otrzymasz kod autoryzacyjny.")
            auth_code = input("Wpisz kod autoryzacyjny: ")
            flow.fetch_token(code=auth_code)
            creds = flow.credentials
            log_message("Nowy token został uzyskany.")

        with open(token_path, 'w') as token:
            token.write(creds.to_json())

        return creds

    def _get_or_create_task_list(self) -> str:
        """Get existing task list ID or create a new one."""
        task_lists = self.service.tasklists().list().execute().get('items', [])
        for task_list in task_lists:
            if task_list['title'] == TASK_LIST_NAME:
                return task_list['id']

        new_list = self.service.tasklists().insert(body={'title': TASK_LIST_NAME}).execute()
        return new_list['id']

    def add_task_if_not_exists(self, event_title: str, event_date: str, notes: str = 'Dodano automatycznie z Librus') -> bool:
        """Add a new task if it doesn't already exist and isn't today."""
        event_datetime = datetime.strptime(event_date, "%Y-%m-%d")
        today = datetime.now().date()

        if event_datetime.date() == today:
            log_message(f"Pomijam wydarzenie z dzisiaj: {event_title}")
            return False

        tasks = self.service.tasks().list(tasklist=self.task_list_id, showCompleted=False).execute().get('items', [])

        for task in tasks:
            if task['title'] == event_title and task['due'].startswith(event_date):
                log_message(f"Już istnieje: {event_title} na {event_date}")
                return False

        due_date = event_datetime.isoformat() + "Z"
        task = {
            'title': event_title,
            'due': due_date,
            'notes': notes
        }
        self.service.tasks().insert(tasklist=self.task_list_id, body=task).execute()
        log_message(f"Dodano nowe: {event_title} na {event_date}")
        return True


class LibrusSync:
    def __init__(self):
        load_dotenv()
        self.username = os.getenv('LIBRUS_LOGIN')
        self.password = os.getenv('LIBRUS_PASSWORD')
        self.tasks_manager = GoogleTasksManager()
        self.all_tasks = []

        if not self.username or not self.password:
            raise ValueError("Brak danych logowania Librus w .env!")

    def process_homework(self, client: Client):
        """Process and sync homework assignments."""
        today = datetime.now()
        date_from = today.replace(day=1).strftime("%Y-%m-%d")
        last_day = (today.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        date_to = last_day.strftime("%Y-%m-%d")

        try:
            homework_assignments = get_homework(client, date_from, date_to)
            for homework in homework_assignments:
                self._process_single_homework(client, homework)

        except Exception as e:
            log_message(f"Błąd podczas przetwarzania zadań: {str(e)}")

    def _process_single_homework(self, client: Client, homework: Homework):
        """Process a single homework assignment."""
        completion_date = homework.completion_date.split()[0]

        try:
            homework_date = datetime.strptime(completion_date, "%Y-%m-%d")
            today = datetime.now().date()

            if homework_date.date() == today:
                log_message(f"Pomijam zadanie domowe z dzisiaj: {homework.lesson}")
                return

            if homework_date.date() < today:
                log_message(f"Pomijam zadanie domowe z przeszłości: {homework.lesson}")
                return

        except ValueError:
            log_message(f"Nieprawidłowy format daty: {homework.completion_date}")
            return

        details = homework_detail(client, homework.href)
        notes = "\n".join([f"{k}: {v}" for k, v in details.items() if v])
        event_title = f"zadanie - {homework.lesson}"

        self.all_tasks.append({
            'title': event_title,
            'date': completion_date,
            'notes': notes
        })

    def process_schedule(self, client: Client):
        """Process and sync schedule events."""
        current_date = datetime.now()
        month = current_date.strftime("%m")
        year = current_date.strftime("%Y")
        schedule = get_schedule(client, month, year, include_empty=True)

        for day, events in schedule.items():
            if events:
                self._process_day_events(events, day, month, year)

    def _process_day_events(self, events: List, day: int, month: str, year: str):
        """Process events for a single day."""
        for event in events:
            if not event.title:
                continue

            if not any(keyword in event.title.lower() for keyword in TEST_KEYWORDS):
                continue

            event_date = f"{year}-{month}-{str(day).zfill(2)}"
            if datetime.strptime(event_date, "%Y-%m-%d") < datetime.now() - timedelta(days=1):
                continue

            self._add_event_task(event, event_date)

    def _add_event_task(self, event: any, event_date: str):
        """Add a single event as a task."""
        notes = []
        if event.data and isinstance(event.data, dict):
            notes = [f"{k}: {v}" for k, v in event.data.items() if v and v != "unknown"]

        event_title = f"{event.title} - {event.subject}" if event.subject else event.title
        if event.hour and event.hour != "unknown":
            event_title += f" ({event.hour})"

        self.all_tasks.append({
            'title': event_title,
            'date': event_date,
            'notes': "\n".join(notes) if notes else "Brak dodatkowych informacji"
        })

    def process_collected_tasks(self) -> int:
        """Sort and add collected tasks in chronological order. Returns the number of tasks added."""
        self.all_tasks.sort(key=lambda task: task['date'], reverse=True)
        added_count = 0
        for task in self.all_tasks:
            added = self.tasks_manager.add_task_if_not_exists(
                task['title'],
                task['date'],
                notes=task['notes']
            )
            if added:
                added_count += 1
        return added_count


def send_discord_embed(title: str, description: str, color: int):
    """Wysyła embed na Discord poprzez webhook."""
    webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
    if not webhook_url:
        log_message("Brak konfiguracji webhooka Discord. Wiadomość nie została wysłana.")
        return

    # Przycinanie opisu jeśli przekracza limit
    max_desc_length = 4096
    if len(description) > max_desc_length:
        description = description[:max_desc_length - 3] + "..."

    embed = {
        "title": title,
        "description": description,
        "color": color,
        "timestamp": datetime.now().isoformat()
    }

    payload = {
        "embeds": [embed]
    }

    try:
        response = requests.post(
            webhook_url,
            json=payload,
            headers={'Content-Type': 'application/json'}
        )
        if response.status_code == 204:
            log_message("Wysłano wiadomość na Discord.")
        else:
            log_message(f"Błąd przy wysyłaniu na Discord: {response.status_code}")
    except Exception as e:
        log_message(f"Błąd wysyłania na Discord: {str(e)}")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def main() -> int:
    """Main function to run the Librus sync process."""
    try:
        current_date_header = datetime.now().strftime("%Y-%m-%d")
        print(f"----------- {current_date_header} ------------")
        
        sync = LibrusSync()
        client = new_client()
        client.get_token(sync.username, sync.password)

        sync.process_schedule(client)
        sync.process_homework(client)
        added_count = sync.process_collected_tasks()
        
        return added_count

    except Exception as e:
        log_message(f"Błąd w głównej funkcji: {str(e)}")
        raise


if __name__ == "__main__":
    try:
        added_count = main()
        success_msg = f"**Synchronizacja zakończona sukcesem!**\nDodano {added_count} nowych wydarzeń."
        send_discord_embed("✅ Sukces", success_msg, 0x00FF00)
        
    except Exception as e:
        error_traceback = traceback.format_exc()
        log_message(f"Całkowity błąd synchronizacji:\n{error_traceback}")
        
        # Formatowanie błędu dla Discord
        error_msg = f"```\n{error_traceback[:1900]}\n```"  # Ograniczenie do 2000 znaków
        send_discord_embed("❌ Błąd Synchronizacji", error_msg, 0xFF0000)