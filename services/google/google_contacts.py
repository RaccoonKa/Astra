import os
import json
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    'https://www.googleapis.com/auth/contacts.readonly',
    'https://www.googleapis.com/auth/youtube.readonly'
]


class GoogleContactsManager:
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        self.config_dir = os.path.join(self.base_dir, "personal_data", "configs", "google")
        os.makedirs(self.config_dir, exist_ok=True)

        self.creds_path = os.path.join(self.config_dir, "credentials.json")
        self.token_path = os.path.join(self.config_dir, "token.json")

    def _get_credentials(self):
        creds = None
        if os.path.exists(self.token_path):
            try:
                creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
            except Exception:
                creds = None

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception:
                    creds = None

            if not creds:
                if not os.path.exists(self.creds_path):
                    print(f"[GOOGLE ERROR]: Файл {self.creds_path} не найден!")
                    return None

                flow = InstalledAppFlow.from_client_secrets_file(self.creds_path, SCOPES)
                creds = flow.run_local_server(port=0)

            with open(self.token_path, 'w', encoding='utf-8') as token_file:
                token_file.write(creds.to_json())

        return creds

    def get_contacts(self):
        creds = self._get_credentials()
        if not creds:
            return []

        try:
            service = build('people', 'v1', credentials=creds)
            results = service.people().connections().list(
                resourceName='people/me',
                pageSize=100,
                personFields='names,phoneNumbers'
            ).execute()

            connections = results.get('connections', [])
            contacts_list = []

            for person in connections:
                names = person.get('names', [])
                phones = person.get('phoneNumbers', [])

                if names and phones:
                    name = names[0].get('displayName')
                    phone = phones[0].get('value')
                    contacts_list.append({'name': name, 'phone': phone})

            return contacts_list
        except Exception as e:
            print(f"[GOOGLE CONTACTS ERROR]: {e}")
            return []

    def find_phone_by_name(self, target_name):
        contacts = self.get_contacts()
        if not contacts or not target_name:
            return None

        target_low = target_name.lower().strip()

        for c in contacts:
            c_name = c['name'].lower()
            if target_low in c_name or c_name in target_low:
                return c['phone']

        return None