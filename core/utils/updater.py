import os
import sys
import tempfile
import subprocess
import requests
from packaging import version
from PyQt6.QtCore import QThread, pyqtSignal

CURRENT_VERSION = "2.0.0"
GITHUB_REPO = "RaccoonKa/Astra"


class UpdateCheckerThread(QThread):
    update_available = pyqtSignal(str, str, str)

    def run(self):
        url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                latest_tag = data.get("tag_name", "").lstrip("v")
                changelog = data.get("body", "")

                download_url = None
                for asset in data.get("assets", []):
                    name = asset.get("name", "").lower()
                    if name.endswith(".msi") or name.endswith(".exe"):
                        download_url = asset.get("browser_download_url")
                        break

                if latest_tag and version.parse(latest_tag) > version.parse(CURRENT_VERSION):
                    if download_url:
                        self.update_available.emit(latest_tag, changelog, download_url)
        except Exception as e:
            print(f"[Update Checker Error]: {e}")


class DownloaderThread(QThread):
    progress_changed = pyqtSignal(int)
    download_finished = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, download_url: str):
        super().__init__()
        self.download_url = download_url

    def run(self):
        try:
            ext = ".msi" if ".msi" in self.download_url.lower() else ".exe"
            temp_path = os.path.join(tempfile.gettempdir(), f"Astra_Update{ext}")

            resp = requests.get(self.download_url, stream=True, timeout=15)
            total_size = int(resp.headers.get('content-length', 0))
            downloaded = 0

            with open(temp_path, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = int((downloaded / total_size) * 100)
                            self.progress_changed.emit(percent)

            self.download_finished.emit(temp_path)
        except Exception as e:
            self.error_occurred.emit(str(e))


def apply_update_and_restart(installer_path: str):
    if installer_path.lower().endswith(".msi"):
        subprocess.Popen(["msiexec.exe", "/i", installer_path])
    else:
        subprocess.Popen([installer_path], shell=True)
    sys.exit(0)
