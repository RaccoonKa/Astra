# 🧪 Astra: Research Laboratory

This is my research sandbox — the heart of the **"Astra"** voice assistant development.  
Here I experiment with architectures, train models to understand user intents, extract entities from speech, and recognize emotions.

This branch contains all the scripts that turn raw data into the assistant's *"brains"*.

---

## 🏗 Project Structure

```plaintext
ml_research/
├── data/                   # Datasets (manually collected intents and dusha for emotions)
├── train_models/           # Training scripts (NLU, Emotions, Joint)
├── results/                # Metrics, Loss plots, and Confusion Matrices
├── prepare_data_files/     # Data preprocessing scripts
├── converter_files/        # Conversion tools
└── optimized_models/       # Ready-to-use ONNX models for fast inference
```

## 🧠 Main Components

### 1. NLU (Natural Language Understanding)

The modules are built on **cointegrated/rubert-tiny2** — the optimal choice for Astra, as it is fast, lightweight, and understands Russian perfectly.

- **Joint NLU** (`train_joint.py`):  
  Multi-task learning. The model simultaneously classifies intent and extracts slots (entities) in a single pass. This saves resources and takes context into account.

- **Slot Filler** (`train_slots.py`):  
  A separate model for high-precision entity extraction (e.g., extracting parameters from long phrases).

---

### 2. Emotion Recognition

Here are three approaches to emotion classification from voice:

| Model | Description |
|-------|-------------|
| **Baseline CNN** | A lightweight convolutional network for fast tasks. |
| **Smart Attentive SE-CRNN** | An advanced model with SE-blocks (Squeeze-and-Excitation) and Temporal Attention to focus on emotionally charged parts of the phrase. |
| **Wav2Vec2 Russian** | A powerful transformer used as a **Teacher model** for knowledge distillation. |

---

### 3. Computer Vision & Fatigue Monitoring

A multi-model computer vision subsystem designed for fatigue diagnostics, biometric owner authentication, and touchless control:

- **Eye State Classifier** (`eye_state_model.onnx`):  
  A custom, lightweight Grayscale (32 * 32 ) CNN running on **ONNX Runtime CPU**. Performs real-time binary classification of eye states (`Open vs Closed`).

- **3D Face Landmark Mesh** (`FaceLandmarker.task`):  
  MediaPipe Tasks API implementation tracking 478 3D facial landmarks. Used for precise anatomical eye localization regardless of head pose, distance, or lighting.

- **Biometric Presence & Security** (`PresenceManager`):  
  Real-time face verification pipeline comparing facial embeddings against owner templates with strict Euclidean distance tolerance (0.5) and automatic screen locking on unauthorized access or absence.  
  `PY`

- **Touchless Gesture Control** (`GestureDetector`):  
  Spatial hand tracking classifying gestures (e.g., fist, open palm, pointing) for media and system navigation.  
  `PY`

---

## 🛠 Tech Stack & Features

I use modern approaches to make Astra not only smarter but also more efficient:

- **Knowledge Distillation**  
  I train lightweight models (CRNN) on the predictions of the heavy model (Wav2Vec2), transferring the "wisdom" of the large model into a compact architecture.

- **Alpha-Focal Loss**  
  A modified loss function for emotion classification. It helps the model not to "stick" on frequent classes (neutral phrases) and better learn rare and complex emotions (anger, joy).

- **ONNX Conversion & Quantization**  
  All trained weights (.pth) are automatically converted to ONNX format with QInt8 quantization.  

  ✅ This reduces model size by 3–4 times and speeds up inference on CPU, making Astra's response nearly instant.

- **3D Landmark Dynamic Scaling (CV Pipeline)**  
  Eliminated bounding box collapse by calculating eye regions proportionally to horizontal inter-canthal width (1.6×), preventing height compression to zero pixels when eyelids shut.

- **Hysteresis Filtering (Anti-Jitter)**  
  Implemented a dual-threshold Schmitt trigger (0.42 closing / 0.30 opening) with decoupled instantaneous blink registration (20–600 ms) and continuous drowsiness tracking (>6s).

- **Lazy Loading Architecture**  
  Zero idle RAM/CPU footprint: neural network runtimes (Face ID, Eye Tracking, Gestures) are instantiated and garbage-collected strictly on demand via modular settings.

---

## 📊 Results & Metrics

Each training run generates reports in the `results/` folder:

- **Confusion Matrix** — a clear error matrix to identify weaknesses in classification.
- **Loss Curves** — training plots to monitor overfitting.
- **Metrics Summary** — files with final Accuracy and F1-score for each model.

---

> ✨ The project is actively evolving. Stay tuned!

---

## 🙏 Special Thanks

I want to express my sincere gratitude to the companies and teams that made this project possible:

---

### 🏦 Sberbank

Huge thanks to **Sberbank** for providing:

- **The dataset** for training emotion and intent recognition models — high-quality labeled data became the foundation for all research work.
- **The Wav2Vec2 Russian model** — a powerful transformer that I use as a **Teacher model** in the knowledge distillation process. Thanks to this model, my lightweight CRNN architecture inherits deep speech patterns while maintaining high inference speed.

---

### 🎙️ Silero

Special thanks to the **Silero** team for:

- **Speech synthesis models** and **voice models** that have become an integral part of the "Astra" voice assistant.
- High-quality and natural-sounding synthesis, available even for local use, which allows Astra to sound lively and human-like.

---

# 🧪 Астра: Лаборатория Исследований

Это моя исследовательская песочница — сердце разработки голосового ассистента **«Астра»**.  
Здесь я экспериментирую с архитектурами, обучаю модели понимать намерения пользователя, выделять сущности в речи и распознавать эмоции.

В этой ветке живут все скрипты, которые превращают сырые данные в *"мозги"* ассистента.

---

## 🏗 Структура проекта

```plaintext
ml_research/
├── data/                   # Датасеты (интенты и dusha для эмоций)
├── train_models/           # Скрипты обучения (NLU, Emotions, Joint)
├── results/                # Метрики, графики Loss и Confusion Matrix
├── prepare_data_files/     # Скрипты предобработки данных
├── converter_files/        # Инструменты для конвертации
└── optimized_models/       # Готовые ONNX-модели для быстрого инференса
```

## 🧠 Основные компоненты

### 1. NLU (Распознавание речи)

Модули построены на базе **cointegrated/rubert-tiny2** — оптимальный выбор для Астры, так как он быстрый, лёгкий и отлично понимает русский язык.

- **Joint NLU** (`train_joint.py`):  
  Мультизадачное обучение. Модель одновременно классифицирует интент (намерение) и находит слоты (сущности) за один проход. Это экономит ресурсы и учитывает контекст.

- **Slot Filler** (`train_slots.py`):  
  Отдельная модель для высокоточного извлечения сущностей (например, параметров из длинных фраз).

---

### 2. Emotion Recognition (Распознавание эмоций)

Здесь собраны три подхода к классификации эмоций из голоса:

| Модель | Описание |
|--------|----------|
| **Baseline CNN** | Лёгкая свёрточная сеть для быстрых задач. |
| **Smart Attentive SE-CRNN** | Продвинутая модель с SE-блоками (Squeeze-and-Excitation) и Temporal Attention для фокусировки на эмоционально окрашенных частях фразы. |
| **Wav2Vec2 Russian** | Мощный трансформер, используемый как **Teacher-модель** для дистилляции знаний. |

---

## 3. Компьютерное зрение и мониторинг усталости (Computer Vision)

Комплексный модуль зрительного восприятия для бесконтактного взаимодействия, биометрической безопасности и контроля здоровья пользователя:

- **Eye State Classifier** (`eye_state_model.onnx`):  
  Кастомная компактная свёрточная нейросеть (32 × 32, Grayscale) на базе **ONNX Runtime**. Выполняет бинарную классификацию состояния глаз (`Open / Closed`) в реальном времени.

- **3D Face Mesh** (`FaceLandmarker.task`):  
  Трекинг 478 трёхмерных ключевых точек лица через MediaPipe Tasks API. Обеспечивает анатомически точную локализацию области глаз при наклонах головы, смещении взгляда на клавиатуру и изменении дистанции до камеры.

- **Биометрия и Face ID** (`PresenceManager`):  
  Сравнение векторных эмбеддингов с эталонными снимками владельца (порог расстояния `0.5`) с автоматической блокировкой системы при обнаружении постороннего или долгом отсутствии.  

- **Распознавание жестов** (`GestureDetector`):  
  Детекция фаланг пальцев и классификация жестов (кулак, открытая ладонь, указательный палец) для управления медиаплеером и блокировкой ПК.  

---

## 🛠 Технологический стек и фишки

Я использую современные подходы, чтобы Астра работала не только умнее, но и эффективнее:

- **Knowledge Distillation**  
  Обучаю лёгкие модели (CRNN) на предсказаниях тяжёлой модели (Wav2Vec2), передавая «мудрость» в компактную архитектуру.

- **Alpha-Focal Loss**  
  Модифицированная функция потерь для классификации эмоций. Помогает модели не «залипать» на частых классах (нейтральные фразы) и лучше выучивать редкие эмоции (гнев, радость).

- **Конвертация в ONNX и квантизация**  
  Все обученные веса (.pth) автоматически конвертируются в формат ONNX с квантизацией QInt8.  

  ✅ Это уменьшает размер модели в 3–4 раза и ускоряет работу на CPU, делая ответ Астры практически мгновенным.

- **Динамическое масштабирование 3D-кропа (CV Pipeline)**  
  Решена проблема схлопывания области глаз: вырез формируется относительно горизонтального расстояния между уголками глаз (1.6×), гарантируя стабильный размер входного тензора даже при сомкнутых веках.

- **Гистерезис против дребезга сигналов (Jitter)**  
  Алгоритм с двойным порогом (триггер Шмитта: 0.42 вход / 0.30 выход) исключает ложные моргания при длительном закрытии глаз и четко разграничивает быстрый блик (20–600 мс) и глубокую сонливость (> 6 с).

- **Lazy Loading и оптимизация ресурсов**
  Полное отсутствие фоновой нагрузки на CPU и RAM: веса нейросетей загружаются и выгружаются сборщиком мусора динамически при включении соответствующих тумблеров в настройках.

---

## 🛠 Технологический стек и фишки

Я использую современные подходы, чтобы Астра работала не только умнее, но и эффективнее:

- **Knowledge Distillation**  
  Обучаю лёгкие модели (CRNN) на предсказаниях тяжёлой модели (Wav2Vec2), передавая «мудрость» в компактную архитектуру.

- **Alpha-Focal Loss**  
  Модифицированная функция потерь для классификации эмоций. Помогает модели не «залипать» на частых классах (нейтральные фразы) и лучше выучивать редкие эмоции (гнев, радость).

- **Конвертация в ONNX**  
  Все обученные веса (`.pth`) автоматически конвертируются в формат **ONNX** с квантизацией **QInt8**.  
  ✅ Это уменьшает размер модели в 3–4 раза и ускоряет работу на CPU, делая ответ Астры практически мгновенным.

---

## 📊 Результаты и Метрики

Каждый запуск обучения генерирует отчёты в папку `results/`:

- **Confusion Matrix** — наглядная матрица ошибок для поиска слабых мест в классификации.
- **Loss Curves** — графики обучения для контроля переобучения.
- **Metrics Summary** — файлы с итоговой точностью (Accuracy) и F1-score для каждой модели.

✨ Проект активно развивается.

---

## 🙏 Особая благодарность

Хочу выразить искреннюю благодарность компаниям и командам, которые сделали этот проект возможным:

---

### 🏦 Сбербанк

Выражаю огромную благодарность **Сбербанку** за предоставление:

- **Датасета** для обучения моделей распознавания эмоций и намерений — качественные размеченные данные стали фундаментом для всей исследовательской работы.
- **Модели Wav2Vec2 Russian** — мощного трансформера, который я использую как **Teacher-модель** в процессе дистилляции знаний. Благодаря этой модели моя лёгкая CRNN-архитектура перенимает глубокие паттерны речи, сохраняя при этом высокую скорость работы.

---

### 🎙️ Silero

Отдельное спасибо команде **Silero** за:

- **Модели синтеза речи** и **голосовые модели**, которые стали неотъемлемой частью голосового ассистента «Астра».  
- Высококачественный и естественный синтез, доступный даже для локального использования, что позволяет Астре звучать живо и человечно.

---