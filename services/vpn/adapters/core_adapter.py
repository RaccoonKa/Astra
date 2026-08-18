import os
import subprocess
import psutil
import winreg


class CoreAdapter:
    def __init__(self):
        pass

    def set_system_proxy(self, enable: bool, host: str = "127.0.0.1", port: int = 10809):
        try:
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
            if enable:
                winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1)
                winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, f"{host}:{port}")
            else:
                winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 0)
            winreg.CloseKey(key)
        except Exception as e:
            print(f"[CoreAdapter Proxy Error]: {e}")

    def is_process_running(self, process_name: str) -> bool:
        for proc in psutil.process_iter(['name']):
            try:
                if proc.info['name'] and proc.info['name'].lower() == process_name.lower():
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False

    def kill_process(self, process_name: str):
        for proc in psutil.process_iter(['name']):
            try:
                if proc.info['name'] and proc.info['name'].lower() == process_name.lower():
                    proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        subprocess.run(["taskkill", "/F", "/IM", process_name, "/T"], capture_output=True, creationflags=0x08000000)

    def connect_wireguard(self, tunnel_name: str = ""):
        try:
            cmd = f'wireguard /installtunnelservice "{tunnel_name}"' if tunnel_name else 'wireguard'
            subprocess.Popen(cmd, shell=True, creationflags=0x08000000)
            return "Подключаю WireGuard"
        except Exception as e:
            return f"Ошибка WireGuard: {e}"

    def disconnect_wireguard(self, tunnel_name: str = ""):
        try:
            if tunnel_name:
                subprocess.Popen(f'wireguard /uninstalltunnelservice "{tunnel_name}"', shell=True, creationflags=0x08000000)
            else:
                self.kill_process("wireguard.exe")
            return "WireGuard отключен"
        except Exception as e:
            return f"Ошибка отключения WireGuard: {e}"

    def connect_v2ray(self, v2ray_exe_path: str, config_path: str = ""):
        if not os.path.exists(v2ray_exe_path):
            return "Исполняемый файл V2Ray не найден"
        try:
            cmd = f'"{v2ray_exe_path}" run'
            if config_path and os.path.exists(config_path):
                cmd += f' -c "{config_path}"'
            subprocess.Popen(cmd, cwd=os.path.dirname(v2ray_exe_path), shell=True, creationflags=0x08000000)
            self.set_system_proxy(True)
            return "V2Ray запущен"
        except Exception as e:
            return f"Ошибка запуска V2Ray: {e}"

    def disconnect_v2ray(self):
        self.kill_process("v2ray.exe")
        self.kill_process("xray.exe")
        self.set_system_proxy(False)
        return "V2Ray выключен"