import shutil
from pathlib import Path
from onnxruntime.quantization import quantize_dynamic, QuantType


def quantize_piper_model(input_onnx: str, output_onnx: str):
    input_path = Path(input_onnx).resolve()
    output_path = Path(output_onnx).resolve()

    if not input_path.exists():
        print(f"Ошибка: исходный файл не найден по пути {input_path}")
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Квантование: {input_path.name} -> {output_path.name}...")
    quantize_dynamic(
        model_input=str(input_path),
        model_output=str(output_path),
        weight_type=QuantType.QInt8
    )

    possible_json = [
        Path(str(input_path) + ".json"),
        input_path.with_suffix(".json")
    ]

    found_json = None
    for j in possible_json:
        if j.exists():
            found_json = j
            break

    if found_json:
        target_json = Path(str(output_path) + ".json")
        shutil.copy2(found_json, target_json)
        print(f"Конфиг скопирован: {target_json.name}")
    else:
        print("Внимание: json-конфиг для модели не найден!")

    raw_mb = input_path.stat().st_size / (1024 * 1024)
    int8_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"Успешно сжато! {raw_mb:.1f} MB -> {int8_mb:.1f} MB")


if __name__ == "__main__":
    raw_path = "optimized_models/whisper_tts/astra_whisper.onnx"
    int8_path = "optimized_models/whisper_tts/astra_whisper_int8.onnx"
    quantize_piper_model(raw_path, int8_path)