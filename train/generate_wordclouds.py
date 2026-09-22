import json
import sys
from pathlib import Path
from datasets import load_from_disk
from wordcloud import WordCloud
import matplotlib.pyplot as plt

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR / "train"))

from config import DATASET_DIR, CUSTOM_DATASET_PATH, OUTPUT_DIR, RAW_GO_EMOTIONS, RAW_TO_MACRO, EMOTIONS

CLOUDS_DIR = OUTPUT_DIR / "wordclouds"

RU_STOPWORDS = {
    "и", "в", "во", "не", "что", "он", "на", "я", "с", "со", "как", "а", "то", "все",
    "она", "так", "его", "но", "да", "ты", "к", "у", "же", "вы", "за", "бы", "по",
    "только", "ее", "мне", "было", "вот", "от", "меня", "еще", "нет", "о", "из", "ему",
    "теперь", "когда", "даже", "ну", "вдруг", "ли", "если", "уже", "или", "ни", "быть",
    "был", "него", "до", "вас", "нибудь", "опять", "уж", "вам", "ведь", "там", "потом",
    "себя", "ничего", "ей", "может", "они", "тут", "где", "есть", "надо", "ней", "для",
    "мы", "тебя", "их", "чем", "была", "сам", "чтоб", "без", "будто", "чего", "раз",
    "тоже", "себе", "под", "будет", "ж", "тогда", "кто", "этот", "того", "потому", "этого",
    "какой", "совсем", "ним", "здесь", "этом", "один", "почти", "мой", "тем", "чтобы",
    "нее", "сейчас", "были", "куда", "зачем", "всех", "никогда", "можно", "при", "наконец",
    "два", "об", "другой", "хоть", "после", "над", "больше", "тот", "через", "эти", "нас",
    "про", "всего", "них", "какая", "много", "разве", "три", "эту", "моя", "впрочем", "хорошо", "свою", "этой", "перед",
    "иногда", "лучше", "чуть", "том", "нельзя"
}


def generate_clouds():
    CLOUDS_DIR.mkdir(parents=True, exist_ok=True)
    dataset = load_from_disk(str(DATASET_DIR))
    train_data = dataset["train"]

    emotion_texts = {emo: [] for emo in EMOTIONS}

    for row in train_data:
        text = row.get("ru_text") or row.get("text")
        if not text:
            continue
        labels = row.get("labels", [])
        for l in labels:
            if isinstance(l, int) and l < len(RAW_GO_EMOTIONS):
                raw_name = RAW_GO_EMOTIONS[l]
                macro_name = RAW_TO_MACRO.get(raw_name)
                if macro_name in emotion_texts:
                    emotion_texts[macro_name].append(text)

    if CUSTOM_DATASET_PATH.exists():
        with open(CUSTOM_DATASET_PATH, "r", encoding="utf-8") as f:
            custom_data = json.load(f)

        for item in custom_data:
            text = item.get("text", "").strip()
            if not text:
                continue
            for emo in item.get("emotions", []):
                macro = RAW_TO_MACRO.get(emo, emo)
                if macro in ("sarcasm_annoyance", "anger"):
                    macro = "negative_sarcasm"
                if macro in emotion_texts:
                    emotion_texts[macro].append(text)

    for emo, texts in emotion_texts.items():
        if not texts:
            continue

        full_text = " ".join(texts)
        wc = WordCloud(
            width=800,
            height=400,
            background_color="white",
            colormap="magma" if emo == "negative_sarcasm" else "viridis",
            stopwords=RU_STOPWORDS,
            max_words=100
        ).generate(full_text)

        plt.figure(figsize=(10, 5))
        plt.imshow(wc, interpolation="bilinear")
        plt.axis("off")
        plt.title(f"Облако слов: {emo}", fontsize=16)

        save_file = CLOUDS_DIR / f"wordcloud_{emo}.png"
        plt.savefig(save_file, dpi=300, bbox_inches="tight")
        plt.close()
        print(f"Сохранено облако для '{emo}': {save_file}")


if __name__ == "__main__":
    generate_clouds()