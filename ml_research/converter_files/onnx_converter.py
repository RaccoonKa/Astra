import os
import shutil
import json
import torch
import torch.nn as nn
from onnxruntime.quantization import quantize_dynamic, QuantType
from transformers import AutoTokenizer, BertModel, BertPreTrainedModel, AutoModelForTokenClassification

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR) if os.path.basename(SCRIPT_DIR) == "ml_research" else SCRIPT_DIR
MODELS_DIR = os.path.join(PROJECT_ROOT, "models")
OPTIMIZED_DIR = os.path.join(PROJECT_ROOT, "optimized_models")

os.makedirs(OPTIMIZED_DIR, exist_ok=True)


# Родная архитектура Joint RuBERT NLU
class JointRuBertNLU(BertPreTrainedModel):
    def __init__(self, config, num_intents=1, num_slots=1):
        super().__init__(config)
        self.bert = BertModel(config)
        self.dropout = nn.Dropout(config.hidden_dropout_prob)
        self.intent_classifier = nn.Linear(config.hidden_size, num_intents)
        self.slot_classifier = nn.Linear(config.hidden_size, num_slots)
        self.post_init()

    def forward(self, input_ids, attention_mask=None):
        outputs = self.bert(input_ids, attention_mask=attention_mask)
        sequence_output = outputs[0]
        pooled_output = outputs[1]  # Полноценный BertPooler (Dense + Tanh)

        intent_logits = self.intent_classifier(pooled_output)
        slot_logits = self.slot_classifier(sequence_output)
        return intent_logits, slot_logits


def export_joint_nlu():
    src_dir = os.path.join(MODELS_DIR, "joint_nlu")
    dst_dir = os.path.join(OPTIMIZED_DIR, "joint_nlu")

    if not os.path.exists(src_dir):
        print(f"Пропуск Joint NLU: папка {src_dir} не найдена.")
        return

    print("\n[1/4] Конвертация Joint NLU в ONNX...")
    os.makedirs(dst_dir, exist_ok=True)
    raw_onnx = os.path.join(dst_dir, "model_raw.onnx")
    quant_onnx = os.path.join(dst_dir, "model_quant.onnx")

    cfg_path = os.path.join(src_dir, "nlu_config.json")
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
        num_intents = len(cfg.get("id2intent", cfg.get("intent2id", {})))
        num_slots = len(cfg.get("id2slot", cfg.get("slot2id", {})))

    tokenizer = AutoTokenizer.from_pretrained(src_dir, local_files_only=True)
    model = JointRuBertNLU.from_pretrained(
        src_dir,
        num_intents=num_intents,
        num_slots=num_slots,
        local_files_only=True
    )
    model.eval()

    inputs = tokenizer("какая погода в москве", return_tensors="pt")

    torch.onnx.export(
        model,
        (inputs["input_ids"], inputs["attention_mask"]),
        raw_onnx,
        input_names=["input_ids", "attention_mask"],
        output_names=["intent_logits", "slot_logits"],
        dynamic_axes={
            "input_ids": {0: "batch_size", 1: "sequence_length"},
            "attention_mask": {0: "batch_size", 1: "sequence_length"},
            "intent_logits": {0: "batch_size"},
            "slot_logits": {0: "batch_size", 1: "sequence_length"}
        },
        opset_version=14
    )

    quantize_dynamic(raw_onnx, quant_onnx, weight_type=QuantType.QInt8)
    if os.path.exists(raw_onnx):
        os.remove(raw_onnx)

    for file_name in os.listdir(src_dir):
        if file_name.endswith(".json"):
            shutil.copy(os.path.join(src_dir, file_name), os.path.join(dst_dir, file_name))

    print(f"Joint NLU успешно квантован: {quant_onnx}")


# Экспорт Slot Filler
def export_slot_filler():
    src_dir = os.path.join(MODELS_DIR, "slot_filler")
    dst_dir = os.path.join(OPTIMIZED_DIR, "slot_filler")

    if not os.path.exists(src_dir):
        print(f"Пропуск Slot Filler: папка {src_dir} не найдена.")
        return

    print("\n[2/4] Конвертация Slot Filler в ONNX...")
    os.makedirs(dst_dir, exist_ok=True)
    raw_onnx = os.path.join(dst_dir, "model_raw.onnx")
    quant_onnx = os.path.join(dst_dir, "model_quant.onnx")

    tokenizer = AutoTokenizer.from_pretrained(src_dir, local_files_only=True)
    model = AutoModelForTokenClassification.from_pretrained(src_dir, local_files_only=True)
    model.eval()

    inputs = tokenizer("поставь таймер на пять минут", return_tensors="pt")

    torch.onnx.export(
        model,
        (inputs["input_ids"], inputs["attention_mask"]),
        raw_onnx,
        input_names=["input_ids", "attention_mask"],
        output_names=["slot_logits"],
        dynamic_axes={
            "input_ids": {0: "batch_size", 1: "sequence_length"},
            "attention_mask": {0: "batch_size", 1: "sequence_length"},
            "slot_logits": {0: "batch_size", 1: "sequence_length"}
        },
        opset_version=14
    )

    quantize_dynamic(raw_onnx, quant_onnx, weight_type=QuantType.QInt8)
    if os.path.exists(raw_onnx):
        os.remove(raw_onnx)

    for file_name in os.listdir(src_dir):
        if file_name.endswith(".json"):
            shutil.copy(os.path.join(src_dir, file_name), os.path.join(dst_dir, file_name))

    print(f"Slot Filler сохранён в {quant_onnx}")


# Экспорт Emotion CRNN
class SEBlock(nn.Module):
    def __init__(self, channels, reduction=8):
        super().__init__()
        self.fc = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),
            nn.Flatten(),
            nn.Linear(channels, channels // reduction, bias=False),
            nn.ReLU(inplace=True),
            nn.Linear(channels // reduction, channels, bias=False),
            nn.Sigmoid()
        )

    def forward(self, x):
        b, c, _, _ = x.shape
        weight = self.fc(x).view(b, c, 1, 1)
        return x * weight


class TemporalAttention(nn.Module):
    def __init__(self, hidden_dim):
        super().__init__()
        self.attn = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.Tanh(),
            nn.Linear(hidden_dim // 2, 1)
        )

    def forward(self, x):
        scores = self.attn(x)
        weights = torch.softmax(scores, dim=1)
        return torch.sum(x * weights, dim=1)


class SmartEmotionSECRNN(nn.Module):
    def __init__(self, in_channels=3, num_classes=5):
        super().__init__()
        self.conv1 = nn.Sequential(
            nn.Conv2d(in_channels, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ELU(),
            nn.MaxPool2d((2, 2)),
            nn.Dropout2d(0.1)
        )
        self.se1 = SEBlock(32)

        self.conv2 = nn.Sequential(
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ELU(),
            nn.MaxPool2d((2, 2)),
            nn.Dropout2d(0.15)
        )
        self.se2 = SEBlock(64)

        self.conv3 = nn.Sequential(
            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.BatchNorm2d(128),
            nn.ELU(),
            nn.MaxPool2d((2, 1)),
            nn.Dropout2d(0.2)
        )
        self.se3 = SEBlock(128)

        self.gru = nn.GRU(
            input_size=128 * 16,
            hidden_size=128,
            num_layers=2,
            batch_first=True,
            bidirectional=True,
            dropout=0.25
        )

        self.attention = TemporalAttention(hidden_dim=128 * 2)
        self.fc = nn.Sequential(
            nn.Linear(128 * 2, 64),
            nn.ELU(),
            nn.Dropout(0.35),
            nn.Linear(64, num_classes)
        )

    def forward(self, x):
        x = self.se1(self.conv1(x))
        x = self.se2(self.conv2(x))
        x = self.se3(self.conv3(x))

        b, c, f, t = x.shape
        x = x.permute(0, 3, 1, 2).contiguous().view(b, t, c * f)

        gru_out, _ = self.gru(x)
        attended = self.attention(gru_out)
        return self.fc(attended)


def export_emotion_crnn():
    src_pth = os.path.join(MODELS_DIR, "emotion_crnn", "model_crnn.pth")
    dst_dir = os.path.join(OPTIMIZED_DIR, "emotion_crnn")
    os.makedirs(dst_dir, exist_ok=True)

    if not os.path.exists(src_pth):
        print(f"Пропуск Emotion CRNN: веса {src_pth} не найдены.")
        return

    print("\n[3/4] Конвертация Smart Emotion SE-CRNN в ONNX...")
    raw_onnx = os.path.join(dst_dir, "model_raw.onnx")
    quant_onnx = os.path.join(dst_dir, "model_crnn_quant.onnx")

    model = SmartEmotionSECRNN(in_channels=3, num_classes=5)
    model.load_state_dict(torch.load(src_pth, map_location="cpu", weights_only=True))
    model.eval()

    dummy_input = torch.randn(1, 3, 128, 200)

    torch.onnx.export(
        model,
        dummy_input,
        raw_onnx,
        input_names=["mel_spectrogram"],
        output_names=["emotion_logits"],
        dynamic_axes={
            "mel_spectrogram": {0: "batch_size", 3: "time_frames"},
            "emotion_logits": {0: "batch_size"}
        },
        opset_version=14
    )

    quantize_dynamic(raw_onnx, quant_onnx, weight_type=QuantType.QInt8)
    if os.path.exists(raw_onnx):
        os.remove(raw_onnx)

    print(f"Emotion CRNN сохранена в {quant_onnx}")


# Настройка Silero TTS
def setup_silero_tts():
    dst_dir = os.path.join(OPTIMIZED_DIR, "silero_tts")
    os.makedirs(dst_dir, exist_ok=True)

    src_pt = os.path.join(MODELS_DIR, "v4_ru.pt")
    dst_pt = os.path.join(dst_dir, "v4_ru.pt")

    print("\n[4/4] Настройка Silero TTS...")
    if os.path.exists(src_pt):
        shutil.copy(src_pt, dst_pt)
        print(f"Модель Silero TTS скопирована в {dst_pt}")


if __name__ == "__main__":
    export_joint_nlu()
    export_slot_filler()
    export_emotion_crnn()
    setup_silero_tts()
    print("\nПереконвертация завершена.")