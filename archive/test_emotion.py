import os
import sys
import sounddevice as sd
import librosa

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.nlp.emotion_classifier import EmotionClassifier, EMOTION_TRANSLATION


def record_audio(duration=4, sr=16000):
    print(f"\nЗапись пошла. Говори любую фразу с выражением ({duration} сек)...")

    audio_data = sd.rec(int(duration * sr), samplerate=sr, channels=1, dtype='float32')
    sd.wait()

    print("Запись завершена. Анализирую...")
    return audio_data[:, 0]


def process_folder(classifier, folder_name="test_voices"):
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)
        print(f"\nПапка '{folder_name}' была создана в корне проекта!")
        print("Закинь туда любые .wav, .mp3 или .ogg файлы и выбери этот пункт снова.")
        return

    valid_exts = (".wav", ".mp3", ".ogg", ".flac")
    files = [f for f in os.listdir(folder_name) if f.lower().endswith(valid_exts)]

    if not files:
        print(f"\nВ папке '{folder_name}' пока нет аудиофайлов. Добавь их туда!")
        return

    print(f"\nНайдено файлов: {len(files)}. Начинаем анализ...\n")

    for file in files:
        file_path = os.path.join(folder_name, file)
        try:
            audio_np, _ = librosa.load(file_path, sr=16000, mono=True)

            emotion, confidence = classifier.predict(audio_np)
            ru_emotion = EMOTION_TRANSLATION.get(emotion, emotion)

            print(f"Файл: {file}")
            print(f"Распознано: {ru_emotion.upper()} (Код: {emotion})")
            print(f"Уверенность: {confidence * 100:.1f}%\n")
        except Exception as e:
            print(f"Ошибка при чтении {file}: {e}\n")


def main():
    print("Загрузка модели эмоций...")

    classifier = EmotionClassifier()

    if getattr(classifier, 'session', None) is None:
        print("Ошибка: Модель не загрузилась! Проверь наличие .onnx файла.")
        return

    print("Модель успешно загружена!")

    while True:
        print("=" * 20)
        print("Выбери действие:")
        print("1 - Записать голос с микрофона")
        print("2 - Проанализировать файлы из папки 'test_voices'")
        print("q - Выход из программы")

        choice = input("\nТвой выбор: ").strip().lower()

        if choice == 'q':
            break
        elif choice == '1':
            audio_np = record_audio()
            emotion, confidence = classifier.predict(audio_np)
            ru_emotion = EMOTION_TRANSLATION.get(emotion, emotion)

            print("-" * 20)
            print(f"Распознано: {ru_emotion.upper()} (Код: {emotion})")
            print(f"Уверенность сети: {confidence * 100:.1f}%")
            print("-" * 20)
        elif choice == '2':
            process_folder(classifier)
        else:
            print("Неизвестная команда, попробуй еще раз.")


if __name__ == "__main__":
    main()