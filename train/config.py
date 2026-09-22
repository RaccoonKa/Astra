from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATASET_DIR = BASE_DIR / "dataset" / "ru_go_emotions"
CUSTOM_DATASET_PATH = BASE_DIR / "dataset" / "custom_emotions.json"
MODEL_INPUT_DIR = BASE_DIR / "models" / "rubert-tiny2"
OUTPUT_DIR = BASE_DIR / "results"
FINAL_MODEL_DIR = BASE_DIR / "models" / "astra_text_emotions"

EMOTIONS = [
    "joy_praise",
    "negative_sarcasm",
    "sadness_fatigue",
    "surprise",
    "neutral"
]

EMOTION2ID = {emo: i for i, emo in enumerate(EMOTIONS)}
ID2EMOTION = {i: emo for i, emo in enumerate(EMOTIONS)}

RU_EMOTIONS = {
    "joy_praise": "радость / похвала",
    "negative_sarcasm": "злость / раздражение / сарказм",
    "sadness_fatigue": "грусть / усталость",
    "surprise": "удивление / восторг",
    "neutral": "нейтрально"
}

RAW_GO_EMOTIONS = [
    "admiration", "amusement", "anger", "annoyance", "approval", "caring",
    "confusion", "curiosity", "desire", "disappointment", "disapproval",
    "disgust", "embarrassment", "excitement", "fear", "gratitude", "grief",
    "joy", "love", "nervousness", "optimism", "pride", "realization",
    "relief", "remorse", "sadness", "surprise", "neutral"
]

RAW_TO_MACRO = {
    "admiration": "joy_praise",
    "amusement": "joy_praise",
    "approval": "joy_praise",
    "caring": "joy_praise",
    "gratitude": "joy_praise",
    "joy": "joy_praise",
    "love": "joy_praise",
    "optimism": "joy_praise",
    "pride": "joy_praise",
    "relief": "joy_praise",

    "anger": "negative_sarcasm",
    "annoyance": "negative_sarcasm",
    "disapproval": "negative_sarcasm",
    "disgust": "negative_sarcasm",

    "disappointment": "sadness_fatigue",
    "embarrassment": "sadness_fatigue",
    "fear": "sadness_fatigue",
    "grief": "sadness_fatigue",
    "nervousness": "sadness_fatigue",
    "remorse": "sadness_fatigue",
    "sadness": "sadness_fatigue",

    "confusion": "surprise",
    "curiosity": "surprise",
    "desire": "surprise",
    "excitement": "surprise",
    "realization": "surprise",
    "surprise": "surprise",

    "neutral": "neutral"
}