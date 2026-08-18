# Исследовательский пайплайн максимальной оптимизации SER:
# Baseline Lightweight CNN
#    python ml_research/train_emotion.py --model_type cnn --epochs 10 --lr 0.001
# Smart Attentive SE-CRNN (3-Ch Mel+Delta+SE-Blocks + Alpha-Focal Loss + Distillation)
#    python ml_research/train_emotion.py --model_type crnn --epochs 25 --lr 0.001 --batch_size 32
# Режим дистилляции (если обучен Wav2Vec2):
#    python ml_research/train_emotion.py --model_type crnn --epochs 25 --lr 0.001 --batch_size 32 --distill
# Wav2Vec2 Russian XLS-R Transformer:
#    python ml_research/train_emotion.py --model_type wav2vec2 --epochs 3 --lr 0.0001 --batch_size 16

import os
import argparse
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import torchaudio
import torchaudio.transforms as T
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import accuracy_score, f1_score, confusion_matrix, classification_report


torch.manual_seed(42)
np.random.seed(42)

EMOTION_LABELS = ["neutral", "happy", "sad", "angry", "other"]
LABEL2ID = {label: i for i, label in enumerate(EMOTION_LABELS)}
ID2LABEL = {i: label for i, label in enumerate(EMOTION_LABELS)}

TARGET_SAMPLE_RATE = 16000
MAX_AUDIO_DURATION_SEC = 4.0
TARGET_SAMPLES = int(TARGET_SAMPLE_RATE * MAX_AUDIO_DURATION_SEC)


# Alpha-Focal Loss и Knowledge Distillation
class AlphaFocalLoss(nn.Module):
    def __init__(self, alpha=None, gamma=2.0, label_smoothing=0.05):
        super().__init__()
        self.alpha = alpha
        self.gamma = gamma
        self.label_smoothing = label_smoothing

    def forward(self, inputs, targets):
        ce_loss = F.cross_entropy(inputs, targets, reduction="none", label_smoothing=self.label_smoothing)
        pt = torch.exp(-ce_loss)
        focal_loss = ((1.0 - pt) ** self.gamma) * ce_loss
        if self.alpha is not None:
            alpha_t = self.alpha[targets]
            focal_loss = alpha_t * focal_loss
        return focal_loss.mean()


class DistillationLoss(nn.Module):
    def __init__(self, base_loss_fn, alpha=0.4, temperature=2.0):
        super().__init__()
        self.base_loss_fn = base_loss_fn
        self.alpha = alpha
        self.temperature = temperature
        self.kl_div = nn.KLDivLoss(reduction="batchmean")

    def forward(self, student_logits, teacher_logits, targets):
        hard_loss = self.base_loss_fn(student_logits, targets)
        soft_student = F.log_softmax(student_logits / self.temperature, dim=-1)
        soft_teacher = F.softmax(teacher_logits / self.temperature, dim=-1)
        soft_loss = self.kl_div(soft_student, soft_teacher) * (self.temperature ** 2)
        return (1.0 - self.alpha) * hard_loss + self.alpha * soft_loss


# SE-Block и Внимание
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


# Baseline Lightweight CNN
class LightweightAudioCNN(nn.Module):
    def __init__(self, num_classes=5):
        super().__init__()
        self.conv_block1 = nn.Sequential(
            nn.Conv2d(1, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(),
            nn.MaxPool2d(2, 2)
        )
        self.conv_block2 = nn.Sequential(
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(),
            nn.MaxPool2d(2, 2)
        )
        self.conv_block3 = nn.Sequential(
            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(),
            nn.AdaptiveAvgPool2d((4, 4))
        )
        self.fc_block = nn.Sequential(
            nn.Linear(128 * 4 * 4, 128),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(128, num_classes)
        )

    def forward(self, x):
        x = self.conv_block1(x)
        x = self.conv_block2(x)
        x = self.conv_block3(x)
        x = x.view(x.size(0), -1)
        return self.fc_block(x)


# Smart Attentive SE-CRNN (3-канальный вход)
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


# Датасет (спектрограммы + поддержка передачи сырого аудио для дистилляции)
class MelSpectrogramDataset(Dataset):
    def __init__(self, df, data_dir, n_mels=128, use_3channel=True, use_augment=False, return_raw=False):
        self.df = df
        self.data_dir = data_dir
        self.use_3channel = use_3channel
        self.use_augment = use_augment
        self.return_raw = return_raw
        self.mel_transform = T.MelSpectrogram(
            sample_rate=TARGET_SAMPLE_RATE,
            n_fft=1024,
            hop_length=320 if n_mels == 128 else 512,
            n_mels=n_mels
        )
        self.amplitude_to_db = T.AmplitudeToDB()
        self.freq_mask = T.FrequencyMasking(freq_mask_param=15)
        self.time_mask = T.TimeMasking(time_mask_param=35)

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        file_path = row["file_path"]
        label = row["label"]

        try:
            speech, sr = torchaudio.load(file_path)
            if speech.shape[0] > 1:
                speech = torch.mean(speech, dim=0, keepdim=True)
            if sr != TARGET_SAMPLE_RATE:
                speech = T.Resample(sr, TARGET_SAMPLE_RATE)(speech)
        except Exception:
            speech = torch.zeros((1, TARGET_SAMPLES))

        if speech.shape[1] > TARGET_SAMPLES:
            speech = speech[:, :TARGET_SAMPLES]
        elif speech.shape[1] < TARGET_SAMPLES:
            pad_len = TARGET_SAMPLES - speech.shape[1]
            speech = torch.nn.functional.pad(speech, (0, pad_len))

        mel_spec = self.mel_transform(speech)
        mel_spec_db = self.amplitude_to_db(mel_spec)

        if self.use_augment:
            mel_spec_db = self.freq_mask(mel_spec_db)
            mel_spec_db = self.time_mask(mel_spec_db)

        if self.use_3channel:
            delta = torchaudio.functional.compute_deltas(mel_spec_db)
            delta2 = torchaudio.functional.compute_deltas(delta)
            features = torch.cat([mel_spec_db, delta, delta2], dim=0)
        else:
            features = mel_spec_db

        if self.return_raw:
            return features, speech.squeeze(0), torch.tensor(label, dtype=torch.long)
        return features, torch.tensor(label, dtype=torch.long)


# Сохранение отчётов и матриц
def save_evaluation_artifacts(all_labels, all_preds, model_name_tag, display_name, results_dir):
    class_indices = list(range(len(EMOTION_LABELS)))
    report_text = classification_report(
        all_labels, all_preds, labels=class_indices, target_names=EMOTION_LABELS, zero_division=0
    )
    report_file = os.path.join(results_dir, f"metrics_{model_name_tag}.txt")
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(f"MODEL: {display_name}\n")
        f.write("=== CLASSIFICATION REPORT ===\n")
        f.write(report_text)

    cm = confusion_matrix(all_labels, all_preds, labels=class_indices)
    plt.figure(figsize=(8, 6))
    cmap = "Blues" if model_name_tag == "cnn" else ("Purples" if model_name_tag == "crnn" else "YlOrBr")
    sns.heatmap(cm, annot=True, fmt="d", cmap=cmap, xticklabels=EMOTION_LABELS, yticklabels=EMOTION_LABELS)
    plt.title(f"Confusion Matrix: {display_name}")
    plt.xlabel("Предсказанная эмоция")
    plt.ylabel("Истинная эмоция")
    plt.tight_layout()
    plt.savefig(os.path.join(results_dir, f"confusion_matrix_{model_name_tag}.png"), dpi=300)
    plt.close()
    print(f"Отчёты и матрица успешно сохранены в: {results_dir}")


# 5. Обучение CNN / CRNN (+ Поддержка Дистилляции)
def train_spectrogram_model(args, train_df, val_df, output_model_dir, results_dir, is_crnn=False):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tag = "crnn" if is_crnn else "cnn"
    name = "Smart Attentive SE-CRNN (Alpha-Focal" + (" + Distillation)" if args.distill else ")") if is_crnn else "Baseline Lightweight CNN"
    n_mels = 128 if is_crnn else 64
    use_3ch = is_crnn
    do_distill = is_crnn and args.distill

    print(f"\nИспользование устройства: {device}")
    print(f"Запуск обучения: [{name}]")

    teacher_model = None
    if do_distill:
        teacher_path = os.path.join(os.path.dirname(output_model_dir), "emotion_wav2vec2")
        if os.path.exists(teacher_path):
            print(f"Загрузка Teacher-модели (Wav2Vec2) из: {teacher_path}")
            from transformers import AutoModelForAudioClassification
            teacher_model = AutoModelForAudioClassification.from_pretrained(teacher_path).to(device)
            teacher_model.eval()
            for p in teacher_model.parameters():
                p.requires_grad = False
        else:
            print("Папка models/emotion_wav2vec2 не найдена. Обучение продолжится без дистилляции.")
            do_distill = False

    train_dataset = MelSpectrogramDataset(
        train_df, args.data_dir, n_mels=n_mels, use_3channel=use_3ch, use_augment=is_crnn, return_raw=do_distill
    )
    val_dataset = MelSpectrogramDataset(
        val_df, args.data_dir, n_mels=n_mels, use_3channel=use_3ch, use_augment=False, return_raw=False
    )

    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=args.batch_size, shuffle=False)

    if is_crnn:
        model = SmartEmotionSECRNN(in_channels=3, num_classes=len(EMOTION_LABELS)).to(device)
        # alpha-веса: 0.8 на neutral (чтобы не забивал), 2.0 на happy, 1.8 на sad, 1.3 на angry
        alpha_weights = torch.tensor([0.8, 2.0, 1.8, 1.3, 1.0], dtype=torch.float).to(device)
        base_criterion = AlphaFocalLoss(alpha=alpha_weights, gamma=2.0, label_smoothing=0.04)

        if do_distill:
            criterion = DistillationLoss(base_loss_fn=base_criterion, alpha=0.45, temperature=2.0)
        else:
            criterion = base_criterion

        optimizer = optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-3)
        scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs, eta_min=1e-5)
    else:
        model = LightweightAudioCNN(num_classes=len(EMOTION_LABELS)).to(device)
        criterion = nn.CrossEntropyLoss()
        optimizer = optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
        scheduler = None

    best_f1 = 0.0

    print(f"Старт эпох обучения ({args.epochs} эпох)...")
    for epoch in range(args.epochs):
        model.train()
        total_loss = 0.0

        for batch_data in train_loader:
            if do_distill:
                mel_specs, raw_audio, labels = batch_data
                mel_specs, raw_audio, labels = mel_specs.to(device), raw_audio.to(device), labels.to(device)
                with torch.no_grad():
                    teacher_out = teacher_model(raw_audio).logits
            else:
                mel_specs, labels = batch_data
                mel_specs, labels = mel_specs.to(device), labels.to(device)

            optimizer.zero_grad()
            outputs = model(mel_specs)

            if do_distill:
                loss = criterion(outputs, teacher_out, labels)
            else:
                loss = criterion(outputs, labels)

            loss.backward()
            if is_crnn:
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=3.0)
            optimizer.step()
            total_loss += loss.item()

        if scheduler is not None:
            scheduler.step()

        model.eval()
        all_preds, all_labels = [], []
        with torch.no_grad():
            for mel_specs, labels in val_loader:
                mel_specs, labels = mel_specs.to(device), labels.to(device)
                outputs = model(mel_specs)
                preds = torch.argmax(outputs, dim=1)
                all_preds.extend(preds.cpu().numpy())
                all_labels.extend(labels.cpu().numpy())

        acc = accuracy_score(all_labels, all_preds)
        f1_weighted = f1_score(all_labels, all_preds, average="weighted", zero_division=0)
        avg_loss = total_loss / len(train_loader)

        print(f"Epoch [{epoch+1:02d}/{args.epochs:02d}] - Loss: {avg_loss:.4f} | Val Acc: {acc:.4f} | Val F1: {f1_weighted:.4f}")

        if f1_weighted > best_f1:
            best_f1 = f1_weighted
            torch.save(model.state_dict(), os.path.join(output_model_dir, f"model_{tag}.pth"))

    print(f"\nОбучение завершено. Лучший Val F1-score: {best_f1:.4f}")
    save_evaluation_artifacts(all_labels, all_preds, tag, name, results_dir)


# Обучение Wav2Vec2 Russian
def train_wav2vec2_pipeline(args, train_df, val_df, output_model_dir, results_dir):
    from transformers import (
        AutoFeatureExtractor, AutoModelForAudioClassification,
        TrainingArguments, Trainer
    )
    from datasets import Dataset

    model_name = "jonatasgrosman/wav2vec2-large-xlsr-53-russian"
    print(f"Загрузка базовой модели: {model_name}...")

    feature_extractor = AutoFeatureExtractor.from_pretrained(model_name)
    model = AutoModelForAudioClassification.from_pretrained(
        model_name,
        num_labels=len(EMOTION_LABELS),
        label2id=LABEL2ID,
        id2label=ID2LABEL,
        use_safetensors=True
    )

    model.freeze_feature_encoder()

    train_ds = Dataset.from_pandas(train_df)
    val_ds = Dataset.from_pandas(val_df)

    def preprocess_fn(examples):
        audio_arrays = []
        for fp in examples["file_path"]:
            try:
                speech, sr = torchaudio.load(fp)
                if speech.shape[0] > 1:
                    speech = torch.mean(speech, dim=0)
                if sr != TARGET_SAMPLE_RATE:
                    speech = T.Resample(sr, TARGET_SAMPLE_RATE)(speech)
                audio_arrays.append(speech.squeeze(0).numpy())
            except Exception:
                audio_arrays.append(np.zeros(TARGET_SAMPLES, dtype=np.float32))

        inputs = feature_extractor(
            audio_arrays,
            sampling_rate=TARGET_SAMPLE_RATE,
            max_length=TARGET_SAMPLES,
            padding="max_length",
            truncation=True
        )
        inputs["label"] = examples["label"]
        return inputs

    print("\nИзвлечение аудио-фичей для Wav2Vec2...")
    train_ds = train_ds.map(preprocess_fn, batched=True, batch_size=32)
    val_ds = val_ds.map(preprocess_fn, batched=True, batch_size=32)

    use_fp16 = torch.cuda.is_available()
    training_args = TrainingArguments(
        output_dir=os.path.join(results_dir, "checkpoints_wav2vec2"),
        eval_strategy="epoch",
        save_strategy="epoch",
        learning_rate=args.lr,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        gradient_accumulation_steps=2,
        num_train_epochs=args.epochs,
        fp16=use_fp16,
        dataloader_num_workers=0,
        eval_accumulation_steps=10,
        load_best_model_at_end=True,
        metric_for_best_model="f1_weighted",
        report_to="none"
    )

    def compute_metrics(eval_pred):
        preds = np.argmax(eval_pred.predictions, axis=1)
        return {
            "accuracy": accuracy_score(eval_pred.label_ids, preds),
            "f1_weighted": f1_score(eval_pred.label_ids, preds, average="weighted", zero_division=0)
        }

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        processing_class=feature_extractor,
        compute_metrics=compute_metrics
    )

    print("\nСтарт быстрого файн-тюнинга Wav2Vec2 Russian...")
    trainer.train()

    model.save_pretrained(output_model_dir)
    feature_extractor.save_pretrained(output_model_dir)

    preds_raw = trainer.predict(val_ds)
    preds = np.argmax(preds_raw.predictions, axis=1)
    save_evaluation_artifacts(preds_raw.label_ids, preds, "wav2vec2", "Wav2Vec2 Russian (Large XLS-R)", results_dir)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model_type",
        type=str,
        choices=["cnn", "crnn", "wav2vec2"],
        default="crnn",
        help="Выбор модели: 'cnn' (baseline), 'crnn' (advanced) или 'wav2vec2' (transformer)"
    )
    parser.add_argument("--data_csv", type=str, default="data/dusha_train.csv")
    parser.add_argument("--data_dir", type=str, default="data")
    parser.add_argument("--epochs", type=int, default=25)
    parser.add_argument("--batch_size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--distill", action="store_true", help="Использовать дистилляцию знаний от Wav2Vec2 Teacher")
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(base_dir)

    csv_path = os.path.join(base_dir, args.data_csv)
    data_folder = os.path.join(base_dir, args.data_dir)
    output_model_dir = os.path.join(project_root, "models", f"emotion_{args.model_type}")
    results_dir = os.path.join(base_dir, "results")

    os.makedirs(output_model_dir, exist_ok=True)
    os.makedirs(results_dir, exist_ok=True)

    if not os.path.exists(csv_path):
        print(f"[ОШИБКА]: Датасет {csv_path} не найден!")
        return

    df = pd.read_csv(csv_path)
    df["label"] = df["emotion"].map(LABEL2ID)
    df = df.dropna(subset=["label"])
    df["label"] = df["label"].astype(int)

    def fix_path(p):
        return p if os.path.isabs(p) else os.path.join(data_folder, p)

    df["file_path"] = df["path"].apply(fix_path)

    train_df = df.sample(frac=0.85, random_state=42)
    val_df = df.drop(train_df.index)

    if args.model_type == "cnn":
        train_spectrogram_model(args, train_df, val_df, output_model_dir, results_dir, is_crnn=False)
    elif args.model_type == "crnn":
        train_spectrogram_model(args, train_df, val_df, output_model_dir, results_dir, is_crnn=True)
    elif args.model_type == "wav2vec2":
        train_wav2vec2_pipeline(args, train_df, val_df, output_model_dir, results_dir)


if __name__ == "__main__":
    main()