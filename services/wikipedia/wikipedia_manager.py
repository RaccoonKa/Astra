import re
import requests


class WikipediaManager:
    def __init__(self, lang="ru"):
        self.lang = lang
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "AstraVoiceAssistant/1.0 (https://github.com; contact@astra.local)"
        })
        self.api_url = f"https://{self.lang}.wikipedia.org/w/api.php"

    def _clean_text(self, text):
        if not text:
            return ""

        text = re.sub(r'\([^)]*\)', '', text)
        text = re.sub(r'\[[^\]]*\]', '', text)
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\s+([.,!?;:])', r'\1', text)
        return text.strip()

    def search(self, query):
        if not query:
            return None

        clean_query = re.sub(r'[^\w\s]', '', query).strip()
        if not clean_query:
            return None

        params = {
            "action": "query",
            "format": "json",
            "prop": "extracts",
            "exintro": 1,
            "explaintext": 1,
            "redirects": 1,
            "generator": "search",
            "gsrsearch": clean_query,
            "gsrlimit": 1
        }

        try:
            resp = self.session.get(self.api_url, params=params, timeout=2.0)
            if resp.status_code == 200:
                data = resp.json()
                pages = data.get("query", {}).get("pages", {})
                if pages:
                    page = list(pages.values())[0]
                    extract = page.get("extract", "")
                    clean_extract = self._clean_text(extract)
                    if clean_extract:
                        sentences = re.split(r'(?<=[.!?])\s+', clean_extract)
                        result = " ".join(sentences[:2])
                        if len(result) > 15:
                            return result
        except Exception as e:
            print(f"[Wikipedia Error]: {e}")

        return None