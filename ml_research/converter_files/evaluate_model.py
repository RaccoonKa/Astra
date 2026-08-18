import os
import torch
import pandas as pd
from torch.utils.data import DataLoader
from sklearn.metrics import confusion_matrix, classification_report
import matplotlib.pyplot as plt
import seaborn as sns

from train_emotion import (
    SmartEmotionSECRNN, MelSpectrogramDataset,
    EMOTION_LABELS, LABEL2ID
)


def evaluate():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(base_dir)

    model_path = os.path.join(project_root, "models", "emotion_crnn", "model_crnn.pth")
    csv_path = os.path.join(base_dir, "data", "dusha_train.csv")
    results_dir = os.path.join(base_dir, "results")
    os.makedirs(results_dir, exist_ok=True)

    if not os.path.exists(model_path):
        print(f"Чекпоинт не найден: {model_path}")
        return

    print("Загрузка весов из {model_path}...")
    model = SmartEmotionSECRNN(in_channels=3, num_classes=len(EMOTION_LABELS)).to(device)
    model.load_state_dict(torch.load(model_path, map_location=device, weights_only=True))
    model.eval()

    df = pd.read_csv(csv_path)
    df["label"] = df["emotion"].map(LABEL2ID)
    df = df.dropna(subset=["label"]).astype({"label": int})
    df["file_path"] = df["path"].apply(lambda p: p if os.path.isabs(p) else os.path.join(base_dir, "data", p))

    train_df = df.sample(frac=0.85, random_state=42)
    val_df = df.drop(train_df.index)

    val_dataset = MelSpectrogramDataset(val_df, os.path.join(base_dir, "data"), n_mels=128, use_3channel=True,
                                        use_augment=False)
    val_loader = DataLoader(val_dataset, batch_size=32, shuffle=False)

    print("Запуск оценки на валидации...")
    all_preds, all_labels = [], []
    with torch.no_grad():
        for mel_specs, labels in val_loader:
            mel_specs, labels = mel_specs.to(device), labels.to(device)
            outputs = model(mel_specs)
            preds = torch.argmax(outputs, dim=1)
            all_preds.extend(preds.cpu().numpy())
            all_labels.extend(labels.cpu().numpy())

    class_indices = list(range(len(EMOTION_LABELS)))
    report_text = classification_report(all_labels, all_preds, labels=class_indices, target_names=EMOTION_LABELS,
                                        zero_division=0)

    with open(os.path.join(results_dir, "metrics_crnn.txt"), "w", encoding="utf-8") as f:
        f.write("MODEL: Smart Attentive SE-CRNN (Resumed Checkpoint)\n")
        f.write("=== CLASSIFICATION REPORT ===\n")
        f.write(report_text)

    cm = confusion_matrix(all_labels, all_preds, labels=class_indices)
    plt.figure(figsize=(8, 6))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Purples", xticklabels=EMOTION_LABELS, yticklabels=EMOTION_LABELS)
    plt.title("Confusion Matrix: Smart SE-CRNN (Recovered)")
    plt.xlabel("Предсказанная эмоция")
    plt.ylabel("Истинная эмоция")
    plt.tight_layout()
    plt.savefig(os.path.join(results_dir, "confusion_matrix_crnn.png"), dpi=300)
    plt.close()

    print("Матрица и отчёт заново сохранены в ml_research/results/")
    print("\n" + report_text)


if __name__ == "__main__":
    evaluate()