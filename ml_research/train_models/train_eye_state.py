import os
import time
import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, random_split, Dataset
from torchvision import datasets, transforms
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score, f1_score


class EyeStateCNN(nn.Module):
    def __init__(self):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(1, 16, kernel_size=3, padding=1),
            nn.BatchNorm2d(16),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2),

            nn.Conv2d(16, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2),

            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2)
        )
        self.classifier = nn.Sequential(
            nn.Dropout(0.3),
            nn.Linear(64 * 4 * 4, 64),
            nn.ReLU(inplace=True),
            nn.Dropout(0.2),
            nn.Linear(64, 2)
        )

    def forward(self, x):
        x = self.features(x)
        x = x.view(x.size(0), -1)
        x = self.classifier(x)
        return x


class TransformedDataset(Dataset):
    def __init__(self, subset, transform=None):
        self.subset = subset
        self.transform = transform

    def __len__(self):
        return len(self.subset)

    def __getitem__(self, idx):
        x, y = self.subset[idx]
        if self.transform:
            x = self.transform(x)
        return x, y


def save_training_plots(history, results_dir):
    epochs = range(1, len(history["train_loss"]) + 1)

    plt.figure(figsize=(12, 5))

    plt.subplot(1, 2, 1)
    plt.plot(epochs, history["train_loss"], label="Train Loss", color="#ff7043", linewidth=2)
    plt.plot(epochs, history["val_loss"], label="Val Loss", color="#42a5f5", linewidth=2)
    plt.title("Динамика потерь (Loss)")
    plt.xlabel("Эпоха")
    plt.ylabel("Loss")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend()

    plt.subplot(1, 2, 2)
    plt.plot(epochs, history["train_acc"], label="Train Acc", color="#66bb6a", linewidth=2)
    plt.plot(epochs, history["val_acc"], label="Val Acc", color="#ab47bc", linewidth=2)
    plt.title("Динамика точности (Accuracy %)")
    plt.xlabel("Эпоха")
    plt.ylabel("Точность (%)")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend()

    plt.tight_layout()
    plot_path = os.path.join(results_dir, "eye_state_training_curves.png")
    plt.savefig(plot_path, dpi=300)
    plt.close()
    print(f"[RESULTS]: График кривых обучения сохранен -> {plot_path}")


def save_confusion_matrix_plot(y_true, y_pred, class_names, results_dir):
    cm = confusion_matrix(y_true, y_pred)

    fig, ax = plt.subplots(figsize=(6, 5))
    cax = ax.matshow(cm, cmap="Blues", alpha=0.85)
    fig.colorbar(cax)

    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            ax.text(
                x=j, y=i, s=str(cm[i, j]),
                va='center', ha='center',
                size=12, weight='bold',
                color="white" if cm[i, j] > cm.max() / 2 else "black"
            )

    ax.set_xticks(range(len(class_names)))
    ax.set_yticks(range(len(class_names)))
    ax.set_xticklabels(class_names)
    ax.set_yticklabels(class_names)
    ax.tick_params(top=False, bottom=True, labeltop=False, labelbottom=True)

    plt.xlabel("Предсказанный класс")
    plt.ylabel("Истинный класс")
    plt.title("Матрица ошибок (Confusion Matrix)", pad=15)

    plt.tight_layout()
    cm_path = os.path.join(results_dir, "eye_state_confusion_matrix.png")
    plt.savefig(cm_path, dpi=300)
    plt.close()
    print(f"[RESULTS]: График матрицы ошибок сохранен -> {cm_path}")


def train():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[TRAIN]: Используем устройство -> {device}")

    base_dir = os.path.dirname(os.path.abspath(__file__))
    dataset_dir = os.path.join(base_dir, "mrleyedataset")
    results_dir = os.path.join(base_dir, "results")
    models_dir = os.path.join(base_dir, "optimized_models")

    os.makedirs(results_dir, exist_ok=True)
    os.makedirs(models_dir, exist_ok=True)

    if not os.path.exists(dataset_dir):
        raise FileNotFoundError(f"Папка датасета не найдена: {dataset_dir}")

    transform_train = transforms.Compose([
        transforms.Grayscale(num_output_channels=1),
        transforms.Resize((32, 32)),
        transforms.RandomHorizontalFlip(p=0.5),
        transforms.RandomRotation(degrees=10),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.5], std=[0.5])
    ])

    transform_val = transforms.Compose([
        transforms.Grayscale(num_output_channels=1),
        transforms.Resize((32, 32)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.5], std=[0.5])
    ])

    full_dataset = datasets.ImageFolder(dataset_dir)
    class_names = full_dataset.classes
    print(f"[DATASET]: Классы -> {class_names}")

    train_size = int(0.85 * len(full_dataset))
    val_size = len(full_dataset) - train_size

    train_subset, val_subset = random_split(
        full_dataset, [train_size, val_size],
        generator=torch.Generator().manual_seed(42)
    )

    train_data = TransformedDataset(train_subset, transform=transform_train)
    val_data = TransformedDataset(val_subset, transform=transform_val)

    train_loader = DataLoader(train_data, batch_size=128, shuffle=True, num_workers=2, pin_memory=True)
    val_loader = DataLoader(val_data, batch_size=256, shuffle=False, num_workers=2, pin_memory=True)

    print(f"[DATASET]: Обучающая выборка: {train_size}, Валидация: {val_size}")

    model = EyeStateCNN().to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.001, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='max', factor=0.5, patience=2)

    epochs = 12
    best_val_acc = 0.0
    best_pt_path = os.path.join(models_dir, "best_eye_model.pt")

    history = {
        "train_loss": [],
        "val_loss": [],
        "train_acc": [],
        "val_acc": []
    }

    for epoch in range(1, epochs + 1):
        start_t = time.time()
        model.train()
        running_loss = 0.0
        correct_train = 0
        total_train = 0

        for images, labels in train_loader:
            images, labels = images.to(device), labels.to(device)

            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()

            running_loss += loss.item() * images.size(0)
            _, predicted = outputs.max(1)
            total_train += labels.size(0)
            correct_train += predicted.eq(labels).sum().item()

        epoch_loss = running_loss / total_train
        epoch_acc = (correct_train / total_train) * 100.0

        model.eval()
        val_loss = 0.0
        correct_val = 0
        total_val = 0

        with torch.no_grad():
            for images, labels in val_loader:
                images, labels = images.to(device), labels.to(device)
                outputs = model(images)
                loss = criterion(outputs, labels)

                val_loss += loss.item() * images.size(0)
                _, predicted = outputs.max(1)
                total_val += labels.size(0)
                correct_val += predicted.eq(labels).sum().item()

        val_loss /= total_val
        val_acc = (correct_val / total_val) * 100.0
        elapsed = time.time() - start_t

        scheduler.step(val_acc)

        history["train_loss"].append(epoch_loss)
        history["val_loss"].append(val_loss)
        history["train_acc"].append(epoch_acc)
        history["val_acc"].append(val_acc)

        print(f"Эпоха [{epoch:02d}/{epochs:02d}] | Время: {elapsed:.1f}с | "
              f"Train Loss: {epoch_loss:.4f} Acc: {epoch_acc:.2f}% | "
              f"Val Loss: {val_loss:.4f} Val Acc: {val_acc:.2f}%")

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            torch.save(model.state_dict(), best_pt_path)
            print(f" -> Сохранена лучшая модель с точностью {best_val_acc:.2f}%")

    print("\n[EVALUATION]: Оценка финальной модели на валидационной выборке...")
    model.load_state_dict(torch.load(best_pt_path))
    model.eval()

    all_targets = []
    all_preds = []

    with torch.no_grad():
        for images, labels in val_loader:
            images = images.to(device)
            outputs = model(images)
            _, predicted = outputs.max(1)

            all_targets.extend(labels.numpy())
            all_preds.extend(predicted.cpu().numpy())

    cls_report = classification_report(all_targets, all_preds, target_names=class_names, digits=4)
    acc = accuracy_score(all_targets, all_preds)
    macro_f1 = f1_score(all_targets, all_preds, average='macro')

    print("\n" + cls_report)

    metrics_txt_path = os.path.join(results_dir, "eye_state_metrics.txt")
    with open(metrics_txt_path, "w", encoding="utf-8") as f:
        f.write("=== EYE STATE MODEL EVALUATION METRICS ===\n\n")
        f.write(f"Validation Accuracy: {acc * 100:.2f}%\n")
        f.write(f"Macro F1-Score: {macro_f1 * 100:.2f}%\n\n")
        f.write(cls_report)
    print(f"[RESULTS]: Текстовый отчет метрик сохранен -> {metrics_txt_path}")

    save_training_plots(history, results_dir)
    save_confusion_matrix_plot(all_targets, all_preds, class_names, results_dir)

    print("\n[EXPORT]: Конвертация лучшей модели в ONNX...")
    model.to("cpu")
    dummy_input = torch.randn(1, 1, 32, 32, requires_grad=False)
    onnx_path = os.path.join(models_dir, "eye_state_model.onnx")

    torch.onnx.export(
        model,
        dummy_input,
        onnx_path,
        export_params=True,
        opset_version=14,
        do_constant_folding=True,
        input_names=['eye_image'],
        output_names=['logits'],
        dynamic_axes={'eye_image': {0: 'batch_size'}, 'logits': {0: 'batch_size'}}
    )
    print(f"[DONE]: Модель сохранена в ONNX -> {onnx_path}")


if __name__ == "__main__":
    train()