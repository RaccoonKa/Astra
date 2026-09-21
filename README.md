## EN version 
---

# Astra TTS — Speech Synthesis Models

A repository with custom speech synthesis models for the **Astra** voice assistant based on the **VITS** architecture of the **Piper TTS** framework.

The project implements two specialized models obtained by transfer learning (fine-tuning) on top of a base Russian-language checkpoint
`ru_RU-irina-medium`:
1. **Astra Voice (Main voice):** clear, confident assistant speech for everyday communication and voicing responses.
2. **Astra Whisper:** a muted, quiet voice for night mode and private notifications.

---

# Model Characteristics Comparison

| Parameter | Astra Voice (Main) | Astra Whisper |
| :--- | :--- | :--- |
| **Base checkpoint** | `ru_RU-irina-medium` | `ru_RU-irina-medium` |
| **Delivery style** | Clear conversational timbre | Intimate quiet whisper |
| **Target ONNX file** | `astra_voice_raw.onnx` | `astra_whisper_raw.onnx` |
| **Starting epoch** | 4149 | 4139 |
| **Final epoch** | 5700 (~1550 new epochs) | 6000 (~1860 new epochs) |
| **Batch size** | 16 | 8 |
| **Sampling rate** | 22,050 Hz (mono) | 22,050 Hz (mono) |

---

# Model 1: Astra Voice (Main voice)

The model is trained on a cleaned dataset of conversational speech without parasitic sounds, sighs, and interjections.

### 1. Export and model files
* The checkpoint is exported by the `quantize/export_voice.py` script.
* Resulting files: `exported/astra_voice_raw.onnx` and `exported/astra_voice_raw.onnx.json`.

### 2. Inference parameters
For the main voice, dynamics and ringing articulation are important:
* `--length_scale 1.0` (standard natural tempo)
* `--noise_scale 0.667` (standard tone variability)
* `--noise_w 0.8` (smooth transitions between words)

### 3. Quick start (CLI):
```bash
echo "Astra's voice module has been successfully activated." | piper \
  --model exported/astra_voice_raw.onnx \
  --output_file test_voice.wav
```

---

# Model 2: Astra Whispering Voice (Whisper)

# Data preparation and training

## 1. Dataset preprocessing

Audio files are brought to a unified format (22.05 kHz, mono), and the markup is saved to `dataset/metadata.csv` in UTF-8 encoding:

```bash
python3 -m piper_train.preprocess \
    --language ru \
    --input-dir dataset \
    --output-dir training_dir \
    --dataset-format ljspeech \
    --sample-rate 22050
```
The base model configuration file is copied to the training directory:

```bash
cp irina.json training_dir/config.json
```

---

## 2. Starting training

Training is launched via a script optimized for Ada Lovelace cores (`torch.set_float32_matmul_precision("high")`):

```bash
python3 train_whisper.py
```

---

## 3. Monitoring metrics

To track loss functions (`loss_mel`, `loss_kl`, `loss_gen`) and spectrograms in real time:

```bash
tensorboard --logdir training_dir
```

The interface is available at `http://localhost:6006`.

---

# Export to ONNX for the assistant

After training is complete, the final checkpoint is exported to a lightweight ONNX graph for integration into the main Astra project:

```bash
python3 -m piper_train.export_onnx \
    training_dir/lightning_logs/version_X/checkpoints/best_or_last.ckpt \
    astra_whisper.onnx
```
```bash
cp training_dir/config.json astra_whisper.onnx.json
```
For synthesis, it is enough to pass the generated pair of astra_whisper.onnx and astra_whisper.onnx.json to the piper-tts runtime.

---

# Training results

Fine-tuning was performed on top of the base checkpoint `ru_RU-irina-medium` by adapting the acoustic distribution to whispering.

| Parameter | Value |
| :--- | :--- |
| **Checkpoint base point** | Epoch 4139 (~465k steps) |
| **Final point** | Epoch 6000 (~494.6k steps) |
| **Fine-tuning epochs completed** | 1861 epochs |
| **Total optimizer steps** | ~29,700 steps |
| **Batch size** | 8 (16 batches per epoch) |
| **Final `loss_disc_all`** | ~1.75 (smooth decline without discriminator collapse) |
| **Final `loss_gen_all`** | ~30–32 (stable generator plateau) |

### Convergence analysis (TensorBoard)
* **`loss_disc_all`:** The discriminator demonstrated stable convergence from initial peaks (>3.2) down to ~1.7–1.8, providing an accurate assessment of the realism of whisper acoustic features.
* **`loss_gen_all`:** After an initial jump, the generator quickly adapted to the noisy spectral structure of the quiet voice and settled into a stable oscillatory corridor of 30–32, preserving clear consonant articulation and the purity of phonetic transitions.

---

# Quick start and model verification

After exporting the model to ONNX, synthesis is performed via the standard Piper CLI or Python API:

### Via terminal:
```bash
echo "Hello, Svetozar! I can now speak in a whisper." | piper \
  --model astra_whisper.onnx \
  --output_file test_whisper.wav
```

---
## RU версия
---

# Astra TTS — Модели синтеза речи

Репозиторий с кастомными моделями синтеза речи для голосового ассистента **Астра** на базе архитектуры **VITS** фреймворка **Piper TTS**.

В проекте реализованы две специализированные модели, полученные методом трансферного обучения (дообучения) поверх базового русскоязычного чекпоинта `ru_RU-irina-medium`:
1. **Astra Voice (Основной голос):** чистая, уверенная речь ассистента для ежедневного общения и озвучивания ответов.
2. **Astra Whisper (Шёпот):** приглушённый тихий голос для ночного режима и приватных уведомлений.

---

# Сравнение характеристик моделей

| Параметр | Astra Voice (Основной) | Astra Whisper (Шёпот) |
| :--- | :--- | :--- |
| **Базовый чекпоинт** | `ru_RU-irina-medium` | `ru_RU-irina-medium` |
| **Стиль подачи** | Чёткий разговорный тембр | Интимный тихий шёпот |
| **Целевой файл ONNX** | `astra_voice_raw.onnx` | `astra_whisper_raw.onnx` |
| **Стартовая эпоха** | 4149 | 4139 |
| **Финальная эпоха** | 5700 (~1550 новых эпох) | 6000 (~1860 новых эпох) |
| **Размер батча** | 16 | 8 |
| **Частота дискретизации** | 22 050 Гц (моно) | 22 050 Гц (моно) |

---

# Модель 1: Astra Voice (Основной голос)

Модель натренирована на вычищенном датасете разговорной речи без паразитных звуков, вздохов и междометий.

### 1. Экспорт и файлы модели
* Чекпоинт экспортируется скриптом `quantize/export_voice.py`.
* Итоговые файлы: `exported/astra_voice_raw.onnx` и `exported/astra_voice_raw.onnx.json`.

### 2. Параметры инференса
Для основного голоса важна динамика и звонкая артикуляция:
* `--length_scale 1.0` (стандартный естественный темп)
* `--noise_scale 0.667` (стандартная вариативность тона)
* `--noise_w 0.8` (плавные переходы между словами)

### 3. Быстрый запуск (CLI):
```bash
echo "Голосовой модуль Астры успешно активирован." | piper \
  --model exported/astra_voice_raw.onnx \
  --output_file test_voice.wav
```

---

# Модель 2: Astra Whispering Voice (Шёпот)

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

---

# Результаты обучения

Дообучение (Fine-tuning) проводилось поверх базового чекпоинта `ru_RU-irina-medium` методом адаптации акустического распределения к шепоту.

| Параметр | Значение |
| :--- | :--- |
| **Базовая точка чекпоинта** | Эпоха 4139 (~465k шагов) |
| **Финальная точка** | Эпоха 6000 (~494.6k шагов) |
| **Пройдено эпох дообучения** | 1861 эпоха |
| **Суммарно шагов оптимизатора** | ~29 700 шагов |
| **Размер батча** | 8 (16 батчей на эпоху) |
| **Итоговый `loss_disc_all`** | ~1.75 (плавное снижение без коллапса дискриминатора) |
| **Итоговый `loss_gen_all`** | ~30–32 (стабильное плато генератора) |

### Анализ сходимости (TensorBoard)
* **`loss_disc_all`:** Дискриминатор продемонстрировал стабильную сходимость с начальных пиков (>3.2) до уровня ~1.7–1.8, обеспечивая точную оценку реалистичности акустических признаков шепота.
* **`loss_gen_all`:** Генератор после первичного скачка быстро адаптировался к шумной спектральной структуре тихого голоса и вышел в устойчивый колебательный коридор 30–32, сохранив четкую артикуляцию согласных и чистоту фонетических переходов.

---

# Быстрый старт и проверка модели

После экспорта модели в ONNX синтез выполняется через стандартный CLI или Python API Piper:

### Через терминал:
```bash
echo "Привет, Светозар! Я теперь умею говорить шёпотом." | piper \
  --model astra_whisper.onnx \
  --output_file test_whisper.wav
```
