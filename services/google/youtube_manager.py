import urllib.parse
import webbrowser
import threading
import time
import pyautogui
from services.google.google_contacts import GoogleContactsManager


class YouTubeManager:
    def __init__(self):
        self.contacts_manager = GoogleContactsManager()

    def _auto_fullscreen(self, delay=2.5):
        time.sleep(delay)
        pyautogui.press('f')

    def search_and_play(self, text="", auto_fullscreen=True):
        stop_words = [
            "астра", "включи", "поставь", "найди", "покажи", "открой",
            "на ютубе", "в ютубе", "ютуб", "видео", "мне", "про", "прохождение"
        ]
        query = text.lower()
        for word in stop_words:
            query = query.replace(word, "")
        query = query.strip()

        if not query:
            webbrowser.open("https://youtube.com")
            return "Открываю Ютуб"

        video_url = None
        title_text = ""

        try:
            creds = self.contacts_manager._get_credentials()
            if creds:
                import googleapiclient.discovery
                youtube = googleapiclient.discovery.build('youtube', 'v3', credentials=creds)
                request = youtube.search().list(
                    part="snippet",
                    q=query,
                    type="video",
                    maxResults=1
                )
                response = request.execute()
                items = response.get("items", [])
                if items:
                    video_id = items[0]["id"]["videoId"]
                    title = items[0]["snippet"]["title"]
                    video_url = f"https://www.youtube.com/watch?v={video_id}"
                    title_text = f"Включаю {title}"
        except Exception as e:
            print(f"[YOUTUBE OAUTH ERROR]: {e}")

        if not video_url:
            encoded_query = urllib.parse.quote(query)
            video_url = f"https://www.youtube.com/results?search_query={encoded_query}"
            title_text = f"Ищу {query} на Ютубе"

        webbrowser.open(video_url)

        if auto_fullscreen and "watch?v=" in video_url:
            threading.Thread(target=self._auto_fullscreen, daemon=True).start()

        return title_text