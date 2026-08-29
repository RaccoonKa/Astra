import os
import sys
from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_submodules,
    collect_dynamic_libs,
    collect_all
)

block_cipher = None
base_dir = os.path.abspath(SPECPATH)

datas = []
binaries = []
hiddenimports = []

vosk_datas, vosk_binaries, vosk_hidden = collect_all('vosk')
datas += vosk_datas
binaries += vosk_binaries
hiddenimports += vosk_hidden

vpn_templates = os.path.join(base_dir, 'services', 'vpn', 'templates')
if os.path.exists(vpn_templates):
    datas.append((vpn_templates, os.path.join('services', 'vpn', 'templates')))

if os.path.exists(os.path.join(base_dir, 'assets')):
    datas.append((os.path.join(base_dir, 'assets'), 'assets'))

if os.path.exists(os.path.join(base_dir, 'optimized_models')):
    datas.append((os.path.join(base_dir, 'optimized_models'), 'optimized_models'))

template_path = os.path.join(base_dir, 'personal_data', 'configs', 'config.template.json')
if os.path.exists(template_path):
    datas.append((template_path, os.path.join('personal_data', 'configs')))

google_creds_path = os.path.join(base_dir, 'personal_data', 'configs', 'google', 'credentials.json')
if os.path.exists(google_creds_path):
    datas.append((google_creds_path, os.path.join('personal_data', 'configs', 'google')))

datas += collect_data_files('transformers')
datas += collect_data_files('torch')
datas += collect_data_files('certifi')
try:
    datas += collect_data_files('face_recognition_models')
except Exception:
    pass

hiddenimports += [
    'pkg_resources',
    'setuptools',
    'face_recognition',
    'face_recognition_models',
    'scipy.signal',
    'sounddevice',
    'soundfile',
    'soundcard',
    'cffi',
    'torch',
    'comtypes',
    'pycaw',
    'aiogram',
    'aiohttp',
    'certifi',
    'requests',
    'qrcode',
    'packaging',
    'packaging.version',
    'packaging.specifiers',
    'packaging.requirements',
    'googleapiclient',
    'google_auth_oauthlib',
    'google.oauth2.credentials',
    'cv2',
    'pyautogui',
    'psutil',
    'PIL',
    'mediapipe'
]

hiddenimports += collect_submodules('core')
hiddenimports += collect_submodules('gui')
hiddenimports += collect_submodules('services')
hiddenimports += collect_submodules('audio')

a = Analysis(
    ['main.py'],
    pathex=[base_dir],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'notebook', 'IPython'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Astra',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(base_dir, 'assets', 'icon', 'ico', 'icon_round.ico')
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Astra'
)