import os
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from onnxruntime.quantization import quantize_dynamic, QuantType

from config import FINAL_MODEL_DIR

def export_and_quantize():
    temp_fp32_path = FINAL_MODEL_DIR / "temp_model.onnx"
    int8_onnx_path = FINAL_MODEL_DIR / "astra_text_emotions_int8.onnx"

    print("Загрузка модели из папки:", FINAL_MODEL_DIR)
    tokenizer = AutoTokenizer.from_pretrained(str(FINAL_MODEL_DIR))
    model = AutoModelForSequenceClassification.from_pretrained(str(FINAL_MODEL_DIR))
    model.eval()

    dummy_text = "Тестовая реплика для проверки Астры"
    inputs = tokenizer(
        dummy_text,
        return_tensors="pt",
        max_length=64,
        padding="max_length",
        truncation=True
    )

    input_names = ["input_ids", "attention_mask"]
    if "token_type_ids" in inputs:
        input_names.append("token_type_ids")

    input_tensors = tuple(inputs[k] for k in input_names)

    dynamic_axes = {k: {0: "batch_size", 1: "sequence_length"} for k in input_names}
    dynamic_axes["logits"] = {0: "batch_size"}

    print("Экспорт в ONNX (FP32, Opset 17)...")
    torch.onnx.export(
        model,
        input_tensors,
        str(temp_fp32_path),
        input_names=input_names,
        output_names=["logits"],
        dynamic_axes=dynamic_axes,
        opset_version=17,
        do_constant_folding=True,
        dynamo=False
    )

    print("Квантование в INT8 (astra_text_emotions_int8)...")
    quantize_dynamic(
        model_input=str(temp_fp32_path),
        model_output=str(int8_onnx_path),
        weight_type=QuantType.QInt8
    )

    if temp_fp32_path.exists():
        temp_fp32_path.unlink()

    int8_size = os.path.getsize(int8_onnx_path) / (1024 * 1024)
    print("\nКвантование успешно завершено!")
    print(f"Файл сохранен: {int8_onnx_path}")
    print(f"Итоговый вес квантованной модели: {int8_size:.2f} МБ")

if __name__ == "__main__":
    export_and_quantize()