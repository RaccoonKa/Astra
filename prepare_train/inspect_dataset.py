from pathlib import Path
from datasets import load_from_disk

BASE_DIR = Path(__file__).resolve().parent.parent
DATASET_DIR = BASE_DIR / "dataset" / "ru_go_emotions"

RU_EMOTIONS = {
    "admiration": "восхищение",
    "amusement": "веселье",
    "anger": "злость",
    "annoyance": "раздражение",
    "approval": "одобрение",
    "caring": "забота",
    "confusion": "замешательство",
    "curiosity": "любопытство",
    "desire": "желание",
    "disappointment": "разочарование",
    "disapproval": "неодобрение",
    "disgust": "отвращение",
    "embarrassment": "смущение",
    "excitement": "восторг",
    "fear": "страх",
    "gratitude": "благодарность",
    "grief": "горе",
    "joy": "радость",
    "love": "любовь",
    "nervousness": "нервозность",
    "optimism": "оптимизм",
    "pride": "гордость",
    "realization": "осознание",
    "relief": "облегчение",
    "remorse": "раскаяние",
    "sadness": "грусть",
    "surprise": "удивление",
    "neutral": "нейтрально"
}

dataset = load_from_disk(str(DATASET_DIR))
train_data = dataset["train"]

labels_info = train_data.features.get("labels")
if hasattr(labels_info, "feature") and hasattr(labels_info.feature, "names"):
    label_names = labels_info.feature.names
elif hasattr(labels_info, "names"):
    label_names = labels_info.names
else:
    label_names = list(RU_EMOTIONS.keys())

print("Доступные эмоции:")
for idx, name in enumerate(label_names):
    ru_name = RU_EMOTIONS.get(name, name)
    print(f"{idx:2d}: {name} -> {ru_name}")

print("\n" + "-" * 25)
print("Примеры")
print("-" * 25)

for i in range(10):
    row = train_data[i]
    text = row.get("ru_text") or row.get("text")
    raw_labels = row.get("labels", [])

    mapped = []
    for l in raw_labels:
        eng_name = label_names[l] if isinstance(l, int) and l < len(label_names) else str(l)
        mapped.append(RU_EMOTIONS.get(eng_name, eng_name))

    print(f"\n[{i + 1}] Фраза: {text}")
    print(f"    Эмоции: {', '.join(mapped)}")