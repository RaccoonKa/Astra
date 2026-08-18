import os
import json
import pickle
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from sklearn.feature_extraction.text import TfidfVectorizer
import matplotlib.pyplot as plt
from wordcloud import WordCloud


class IntentMLP(nn.Module):
    def __init__(self, input_dim, num_classes):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 128),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, num_classes)
        )

    def forward(self, x):
        return self.net(x)


class TextDataset(Dataset):
    def __init__(self, X, y):
        self.X = torch.tensor(X, dtype=torch.float32)
        self.y = torch.tensor(y, dtype=torch.long)

    def __len__(self):
        return len(self.y)

    def __getitem__(self, idx):
        return self.X[idx], self.y[idx]


def generate_wordclouds(data, save_dir):
    wc_dir = os.path.join(save_dir, "wordclouds")
    os.makedirs(wc_dir, exist_ok=True)
    for intent, phrases in data.items():
        text = " ".join(phrases)
        wc = WordCloud(width=800, height=400, background_color="white").generate(text)
        plt.figure(figsize=(10, 5))
        plt.imshow(wc, interpolation="bilinear")
        plt.axis("off")
        plt.title(f"Intent: {intent}")
        plt.savefig(os.path.join(wc_dir, f"{intent}.png"), bbox_inches="tight")
        plt.close()


def plot_loss(loss_history, save_dir):
    plt.figure(figsize=(10, 5))
    plt.plot(loss_history, color="#2b5c8f", linewidth=2, label="CrossEntropy Loss")
    plt.title("Intent Classifier Training Loss")
    plt.xlabel("Epoch")
    plt.ylabel("Loss")
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.legend()
    plt.savefig(os.path.join(save_dir, "loss_history.png"), bbox_inches="tight")
    plt.close()


def train():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    dataset_path = os.path.join(base_dir, "data", "intents.json")
    results_dir = os.path.join(base_dir, "results", "intent_classifier")
    os.makedirs(results_dir, exist_ok=True)

    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    generate_wordclouds(data, results_dir)

    classes = list(data.keys())
    class_to_idx = {c: i for i, c in enumerate(classes)}
    idx_to_class = {i: c for i, c in enumerate(classes)}

    texts = []
    labels = []

    for intent, phrases in data.items():
        for phrase in phrases:
            texts.append(phrase.lower())
            labels.append(class_to_idx[intent])

    vectorizer = TfidfVectorizer(ngram_range=(1, 2), max_features=1000)
    X = vectorizer.fit_transform(texts).toarray()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    torch_dataset = TextDataset(X, labels)
    loader = DataLoader(torch_dataset, batch_size=16, shuffle=True)

    model = IntentMLP(input_dim=X.shape[1], num_classes=len(classes)).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.005)

    loss_history = []
    model.train()
    for epoch in range(150):
        running_loss = 0.0
        for batch_X, batch_y in loader:
            batch_X, batch_y = batch_X.to(device), batch_y.to(device)
            optimizer.zero_grad()
            outputs = model(batch_X)
            loss = criterion(outputs, batch_y)
            loss.backward()
            optimizer.step()
            running_loss += loss.item()
        loss_history.append(running_loss / len(loader))

    plot_loss(loss_history, results_dir)

    root_dir = os.path.abspath(os.path.join(base_dir, ".."))
    models_dir = os.path.join(root_dir, "models", "intent_classifier")
    os.makedirs(models_dir, exist_ok=True)

    torch.save(model.state_dict(), os.path.join(models_dir, "custom_intent.pth"))

    config = {
        "classes": classes,
        "class_to_idx": class_to_idx,
        "idx_to_class": idx_to_class,
        "input_dim": X.shape[1]
    }

    with open(os.path.join(models_dir, "intent_config.json"), "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    with open(os.path.join(models_dir, "vectorizer.pkl"), "wb") as f:
        pickle.dump(vectorizer, f)

    print("[SUCCESS]: Модель успешно обучена и сохранена в models/intent_classifier/")
    print(f"[INFO]: Облака слов и график Loss сохранены в {results_dir}")


if __name__ == "__main__":
    train()