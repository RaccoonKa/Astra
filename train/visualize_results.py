import json
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import torch
from datasets import load_from_disk
from sklearn.metrics import classification_report
from transformers import AutoTokenizer, AutoModelForSequenceClassification

from config import (
    DATASET_DIR,
    FINAL_MODEL_DIR,
    OUTPUT_DIR,
    EMOTIONS,
    RU_EMOTIONS,
    RAW_GO_EMOTIONS,
    RAW_TO_MACRO,
    EMOTION2ID
)


def convert_labels(raw_labels):
    macro_set = set()
    for lbl in raw_labels:
        if isinstance(lbl, int) and lbl < len(RAW_GO_EMOTIONS):
            raw_name = RAW_GO_EMOTIONS[lbl]
            macro_name = RAW_TO_MACRO.get(raw_name)
            if macro_name:
                macro_set.add(macro_name)
        elif isinstance(lbl, str):
            if lbl in EMOTION2ID:
                macro_set.add(lbl)
            elif lbl in RAW_TO_MACRO:
                macro_set.add(RAW_TO_MACRO[lbl])
            elif lbl in ("sarcasm_annoyance", "anger"):
                macro_set.add("negative_sarcasm")

    if not macro_set:
        macro_set.add("neutral")

    return [EMOTION2ID[m] for m in macro_set]


def plot_training_history():
    checkpoint_dir = OUTPUT_DIR / "checkpoints"
    state_files = list(checkpoint_dir.glob("**/trainer_state.json"))
    if not state_files:
        print("Файл trainer_state.json не найден.")
        return

    latest_state = max(state_files, key=lambda p: p.stat().st_mtime)
    with open(latest_state, "r", encoding="utf-8") as f:
        data = json.load(f)

    log_history = data.get("log_history", [])
    train_steps, train_loss = [], []
    eval_steps, eval_loss, eval_f1 = [], [], []

    for entry in log_history:
        step = entry.get("step")
        if "loss" in entry and step is not None:
            train_steps.append(step)
            train_loss.append(entry["loss"])
        if "eval_loss" in entry and step is not None:
            eval_steps.append(step)
            eval_loss.append(entry["eval_loss"])
            if "eval_f1_macro" in entry:
                eval_f1.append(entry["eval_f1_macro"])
            elif "eval_f1_micro" in entry:
                eval_f1.append(entry["eval_f1_micro"])

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    ax1.plot(train_steps, train_loss, label="Train Loss", color="royalblue", alpha=0.7)
    if eval_loss:
        ax1.plot(eval_steps, eval_loss, label="Eval Loss", color="crimson", linewidth=2)
    ax1.set_title("Динамика Loss")
    ax1.set_xlabel("Шаги (Steps)")
    ax1.set_ylabel("Loss")
    ax1.grid(True, linestyle="--", alpha=0.5)
    ax1.legend()

    if eval_f1:
        ax2.plot(eval_steps, eval_f1, label="Eval F1 (Macro)", color="forestgreen", linewidth=2)
        ax2.set_title("Качество модели (F1-score)")
        ax2.set_xlabel("Шаги (Steps)")
        ax2.set_ylabel("F1 Score")
        ax2.grid(True, linestyle="--", alpha=0.5)
        ax2.legend()

    plt.tight_layout()
    plot_path = OUTPUT_DIR / "learning_curves.png"
    plt.savefig(plot_path, dpi=300)
    plt.close()
    print(f"График обучения сохранен: {plot_path}")


def plot_metrics_heatmap():
    if not FINAL_MODEL_DIR.exists():
        print("Финальная модель не найдена.")
        return

    tokenizer = AutoTokenizer.from_pretrained(str(FINAL_MODEL_DIR))
    model = AutoModelForSequenceClassification.from_pretrained(str(FINAL_MODEL_DIR))
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    model.eval()

    base_data = load_from_disk(str(DATASET_DIR))
    val_data = base_data["validation"]

    all_preds = []
    all_targets = []

    print("Расчет корректных метрик на валидации...")
    for item in val_data:
        text = str(item.get("ru_text") or item.get("text") or "").strip()
        raw_labels = item.get("labels", [])

        target_ids = convert_labels(raw_labels)
        target_vec = np.zeros(len(EMOTIONS), dtype=int)
        for idx in target_ids:
            target_vec[idx] = 1
        all_targets.append(target_vec)

        inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=64).to(device)
        with torch.no_grad():
            outputs = model(**inputs)
            probs = torch.sigmoid(outputs.logits)[0].cpu().numpy()
            pred_vec = (probs > 0.35).astype(int)
            all_preds.append(pred_vec)

    all_targets = np.array(all_targets)
    all_preds = np.array(all_preds)

    target_names = [f"{EMOTIONS[i]} ({RU_EMOTIONS.get(EMOTIONS[i], '')})" for i in range(len(EMOTIONS))]
    report = classification_report(all_targets, all_preds, target_names=target_names, output_dict=True, zero_division=0)

    metrics_data = []
    for cls in target_names:
        metrics_data.append([
            report[cls]["precision"],
            report[cls]["recall"],
            report[cls]["f1-score"]
        ])

    plt.figure(figsize=(10, 6))
    sns.heatmap(
        metrics_data,
        annot=True,
        fmt=".2f",
        cmap="Blues",
        xticklabels=["Precision", "Recall", "F1-Score"],
        yticklabels=target_names
    )
    plt.title("Метрики по 5 группам эмоций (Multi-label Evaluation)")
    plt.tight_layout()
    heatmap_path = OUTPUT_DIR / "emotions_metrics_heatmap.png"
    plt.savefig(heatmap_path, dpi=300)
    plt.close()
    print(f"Тепловая карта сохранена: {heatmap_path}")


if __name__ == "__main__":
    plot_training_history()
    plot_metrics_heatmap()