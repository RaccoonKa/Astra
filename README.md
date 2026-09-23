## EN version
---

# 🎙️ ASTRA Voiceprint (TinyECAPA)

An ultra-lightweight voice biometrics and open-set speaker verification engine running in real time. Designed specifically for the **Astra** voice assistant.

The model compresses the incoming audio signal into a compact 192-dimensional timbre vector (voiceprint). Verification is based on computing the cosine similarity between the current audio and the user's dynamic reference.

---

## 🚀 Key Metrics

Thanks to architecture compression and knowledge distillation, the student model has inherited the accuracy of the large `ECAPA-TDNN` model while reducing its size by 50x:

| Metric | Teacher (ECAPA-TDNN) | Student (TinyECAPA ONNX) | Gain |
| :--- | :---: | :---: | :---: |
| **Disk size** | ~83.3 MB | **1.65 MB** | **50x lighter** |
| **Inference (CPU)** | ~70-80 ms | **~7-10 ms** | **8-10x faster** |
| **Quality (EER)** | 0.00% | **0.00%** | No quality loss |
| **Embedding size** | 192 | **192** | 100% compatible |

---

## 🧠 Architecture and Stack

* **Student (`TinyECAPA`)**: a lightweight convolutional network with `SERes2Net` blocks (Squeeze-and-Excitation + multi-scale dilated convolutions) and `AttentiveStatsPool` attention pooling.
* **Loss function**: a combined loss:
  $$\mathcal{L} = 0.1 \cdot \mathcal{L}_{\text{ArcFace}} + 0.9 \cdot (20 \cdot \mathcal{L}_{\text{MSE\_Distill}})$$
* **Distillation**: direct alignment of the student's feature space to the embeddings of a pretrained `ECAPA-TDNN` (SpeechBrain) via weighted MSE.
* **Dataset**: a combined corpus of Russian speech and the English-language LibriSpeech slice (`dev-clean`) for robustness to accents, gender, and microphone variations.

---

## 📁 Project Structure

```text
ASTRA_voiceprint/
├── data/
│   ├── manifest/          # Generated train.csv and val_pairs.csv
│   └── raw/
│       └── speakers/
│           ├── baseline/  # Reference audio for tests
│           └── model_data/# Speaker dataset (folders with 16kHz .wav files)
├── models/
│   ├── exported/          # Ready-to-use ONNX model (tiny_ecapa.onnx)
│   ├── student/           # PyTorch checkpoints and TinyECAPA architecture
│   └── teacher/           # Teacher model weights ECAPA-TDNN
├── notebooks/
│   ├── 01_teacher_eval.ipynb              # Teacher evaluation and baseline EER
│   ├── 02_train_student_scratch.ipynb     # Training the student from scratch
│   ├── 03_train_student_distillation.ipynb# Knowledge distillation (Teacher -> Student)
│   └── 04_final_benchmark_and_onnx.ipynb  # CPU benchmark and ONNX export
├── src/
│   ├── dataset.py         # Data loader, augmentations, and manifest assembly
│   ├── losses.py          # ArcFace implementation and distillation losses
│   └── rename.py          # Preprocessing utilities
└── README.md
```

---
## RU версия
---

# 🎙️ ASTRA Voiceprint (TinyECAPA)

Ультралёгкий движок голосовой биометрии и открытой верификации диктора (Open-Set Speaker Verification) в реальном времени. Разработан специально для голосового ассистента **Astra**.

Модель сжимает входящий аудиосигнал в компактный 192-мерный вектор тембра (voiceprint). Верификация строится на вычислении косинусного сходства между текущим аудио и динамическим эталоном пользователя.

---

## 🚀 Ключевые метрики

Благодаря сжатию архитектуры и дистилляции знаний студент перенял точность большой модели `ECAPA-TDNN`, сократив размер в 50 раз:

| Метрика | Teacher (ECAPA-TDNN) | Student (TinyECAPA ONNX) | Профит |
| :--- | :---: | :---: | :---: |
| **Размер на диске** | ~83.3 МБ | **1.65 МБ** | **x50 легче** |
| **Инференс (CPU)** | ~70-80 мс | **~7-10 мс** | **x8-10 быстрее** |
| **Качество (EER)** | 0.00% | **0.00%** | Без потери качества |
| **Размер эмбеддинга** | 192 | **192** | 100% совместимость |

---

## 🧠 Архитектура и стек

* **Студент (`TinyECAPA`)**: облегчённая сверточная сеть с блоками `SERes2Net` (Squeeze-and-Excitation + multi-scale dilated convolutions) и пулингом внимания `AttentiveStatsPool`.
* **Функция потерь**: комбинированный лосс:
  $$\mathcal{L} = 0.1 \cdot \mathcal{L}_{\text{ArcFace}} + 0.9 \cdot (20 \cdot \mathcal{L}_{\text{MSE\_Distill}})$$
* **Дистилляция**: прямое выравнивание признакового пространства студента под эмбеддинги предобученной `ECAPA-TDNN` (SpeechBrain) через взвешенный MSE.
* **Датасет**: объединённый корпус русской речи и англоязычного среза LibriSpeech (`dev-clean`) для устойчивости к акцентам, полу и вариациям микрофонов.

---

## 📁 Структура проекта

```text
ASTRA_voiceprint/
├── data/
│   ├── manifest/          # Сгенерированные train.csv и val_pairs.csv
│   └── raw/
│       └── speakers/
│           ├── baseline/  # Контрольные аудио для тестов
│           └── model_data/# Датасет дикторов (папки с .wav 16kHz)
├── models/
│   ├── exported/          # Готовая ONNX модель (tiny_ecapa.onnx)
│   ├── student/           # PyTorch чекпоинты и архитектура TinyECAPA
│   └── teacher/           # Веса учительской модели ECAPA-TDNN
├── notebooks/
│   ├── 01_teacher_eval.ipynb              # Оценка учителя и baseline EER
│   ├── 02_train_student_scratch.ipynb     # Обучение студента с нуля
│   ├── 03_train_student_distillation.ipynb# Дистилляция знаний (Teacher -> Student)
│   └── 04_final_benchmark_and_onnx.ipynb  # Бенчмарк на CPU и экспорт в ONNX
├── src/
│   ├── dataset.py         # Загрузчик данных, аугментации и сборка манифестов
│   ├── losses.py          # Реализация ArcFace и лоссов дистилляции
│   └── rename.py          # Утилиты предобработки
└── README.md
```