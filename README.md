# Astra TTS — Whispering Voice Model

Ветка с кастомной моделью шепота для голосового ассистента **Астра** на базе фреймворка **Piper TTS (архитектура VITS)**.

Модель получена методом трансферного обучения (дообучения) базового женского русскоязычного голоса `ru_RU-irina-medium` на специализированном датасете тихого голоса и шепота.

## Характеристики модели

- **Архитектура:** VITS (Variational Inference with adversarial learning for end-to-end Text-to-Speech)
- **Базовый чекпойнт:** `ru_RU-irina-medium`
- **Язык:** Русский (`ru_RU`)
- **Стиль речи:** Шёпот / интимный тихий голос
- **Частота дискретизации:** 22 050 Гц (моно, 16-бит PCM)
- **Целевой формат для рантайма:** ONNX (инференс на CPU/GPU)

---

# Структура проекта

```text
whisper/
├── dataset/
│   ├── wavs/             # Аудиозаписи в формате .wav (22050 Hz, mono)
│   └── metadata.csv      # Разметка в формате LJSpeech (id|текст)
├── training_dir/         # Сгенерированные мел-спектрограммы, фонемы и config.json
│   └── lightning_logs/   # Чекпоинты (.ckpt) и логи TensorBoard
├── piper/                # Исходный код Piper
├── irina.ckpt            # Базовый чекпоинт для дообучения
├── irina.json            # Базовая конфигурация модели
├── train_whisper.py      # Скрипт запуска и конфигурации обучения
└── README.md
```

# Аппаратное и программное окружение

- **ОС**: Windows 11 + WSL2 (Ubuntu Linux)
- **GPU**: NVIDIA GeForce RTX 4060 Laptop GPU
- **Python**: 3.10
- **CUDA / PyTorch**: PyTorch с поддержкой CUDA 12.1
- **Ключевые зависимости**:
  - `piper-train`
  - `pytorch-lightning==1.9.5`
  - `torchmetrics==0.11.4`
  - `numpy==1.26.4`
  - `onnx`

---

# Подготовка данных и обучение

## 1. Предобработка датасета

Файлы аудио приводятся к единому формату (22.05 кГц, моно), разметка сохраняется в `dataset/metadata.csv` в кодировке UTF-8:

```bash
python3 -m piper_train.preprocess \
    --language ru \
    --input-dir dataset \
    --output-dir training_dir \
    --dataset-format ljspeech \
    --sample-rate 22050
```
Конфигурационный файл базовой модели копируется в директорию обучения:

```bash
cp irina.json training_dir/config.json
```

---

## 2. Запуск тренировки

Обучение запускается через сценарий с оптимизацией под ядра Ada Lovelace (`torch.set_float32_matmul_precision("high")`):

```bash
python3 train_whisper.py
```

---

## 3. Мониторинг метрик

Для отслеживания функций потерь (`loss_mel`, `loss_kl`, `loss_gen`) и спектрограмм в реальном времени:

```bash
tensorboard --logdir training_dir
```

Интерфейс доступен по адресу `http://localhost:6006`.

---

# Экспорт в ONNX для ассистента

После завершения обучения финальный чекпоинт экспортируется в легковесный ONNX-граф для интеграции в основной проект Астры:

```bash
python3 -m piper_train.export_onnx \
    training_dir/lightning_logs/version_X/checkpoints/best_or_last.ckpt \
    astra_whisper.onnx
```
```bash
cp training_dir/config.json astra_whisper.onnx.json
```
Для синтеза достаточно передать сгенерированную пару astra_whisper.onnx и astra_whisper.onnx.json в рантайм piper-tts.