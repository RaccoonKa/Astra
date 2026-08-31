import json
from piper import PiperVoice

model_path = "ru_RU-irina-medium.onnx"
config_path = model_path + ".json"

print("⏳ Загружаем Piper...")
voice = PiperVoice(model_path, config_path)

print("\n=== ДОСТУПНЫЕ МЕТОДЫ ===")
for method in dir(voice):
    if not method.startswith("_"):
        print(f" - {method}")

print("\n=== ТЕСТ ГЕНЕРАЦИИ ===")
try:
    result = voice.synthesize("Привет, это проверка")
    print(f"Тип результата: {type(result)}")
    print(f"Значение: {result}")
except Exception as e:
    print(f"Ошибка при вызове synthesize без аргументов: {e}")