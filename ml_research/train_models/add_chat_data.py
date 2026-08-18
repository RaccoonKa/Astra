# Обучаем Астру понимать не только намереня пользователя, но и режим простого трёпа. Научим её понимать обычную болтовню.
# Будем сводить к минимуму ошибочный запуск режима привязки фраз к интентам.
# Генерируем датасет с датасета Амазона для получения рандомных разговорных фраз.

import os
import json
import random

script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(script_dir)

possible_paths = [
    os.path.join(script_dir, "data", "intents_slot_fillings_fixed.json"),
    os.path.join(script_dir, "intents_slot_fillings_fixed.json"),
    os.path.join(project_dir, "data", "intents_slot_fillings_fixed.json"),
]

dataset_path = None
for p in possible_paths:
    if os.path.exists(p):
        dataset_path = p
        break

if not dataset_path:
    raise FileNotFoundError("Файл датасета не найден ни по одному из стандартных путей!")

with open(dataset_path, "r", encoding="utf-8") as f:
    existing_data = json.load(f)

chat_candidates = []

try:
    from datasets import load_dataset

    try:
        ds = load_dataset("mteb/amazon_massive_intent", "ru", split="train")
    except Exception:
        ds = load_dataset("AmazonScience/massive", "ru-RU", split="train", trust_remote_code=True)

    for item in ds:
        intent_str = str(item.get("intent", ""))
        text = item.get("utt", item.get("text", "")).lower().strip()
        if text and any(k in intent_str for k in ["smalltalk", "social", "general", "qa"]):
            chat_candidates.append(text)
except Exception:
    pass

if len(chat_candidates) < 200:
    fallback_phrases = [
        "привет как дела", "что нового", "чем занимаешься", "расскажи шутку", "как жизнь",
        "как настроение", "ты кто такая", "кто тебя создал", "сколько тебе лет", "ты робот",
        "какая у тебя любимая музыка", "что делаешь вечером", "мне скучно", "поговори со мной",
        "поболтаем", "расскажи анекдот", "ты умеешь думать", "что ты думаешь о людях",
        "люблю тебя", "ты лучшая", "спасибо за помощь", "ты молодец", "как тебя зовут",
        "откуда ты", "что ты умеешь", "посоветуй фильм", "какой твой любимый цвет",
        "я устал", "тяжелый день был", "все хорошо", "у меня все отлично", "да так ничего особенного",
        "потихоньку", "нормально", "все норм", "не жалуюсь", "все супер", "да пойдет",
        "что посоветуешь почитать", "расскажи интересную историю", "ты спишь", "чем увлекаешься",
        "какое твое любимое блюдо", "ты веришь в инопланетян", "как пройти в библиотеку",
        "почему небо синее", "что такое любовь", "в чем смысл жизни", "какой сегодня день",
        "сколько будет два плюс два", "ты знала что сегодня праздник", "посоветуй что посмотреть",
        "какая твоя мечта", "у тебя есть друзья", "расскажи стишок", "ты любишь котиков",
        "какая у тебя погода", "я пошел спать", "спокойной ночи", "доброе утро", "добрый вечер",
        "хорошего дня", "увидимся позже", "до связи", "пока пока", "приятно познакомиться",
        "ты смешная", "мне грустно", "подними мне настроение", "расскажи что то интересное",
        "ты умеешь петь", "станцуй что нибудь", "кто твой хозяин", "где ты живешь",
        "я пришел домой", "я на работе", "учусь в университете", "пишу диплом", "делаю проект",
        "скоро сессия", "хочу в отпуск", "скорее бы выходные", "какая сегодня дата",
        "что думаешь про искусственный интеллект", "ты заменишь людей", "как дела на работе",
        "все нормально братан", "давай пообщаемся", "что скажешь", "какие новости"
    ]

    variations = ["астра ", "слушай ", "слушай астра ", "эй ", "", "ну ", "скажи "]
    expanded = []
    for ph in fallback_phrases:
        for v in variations:
            expanded.append(f"{v}{ph}".strip())

    chat_candidates.extend(expanded)

random.seed(42)
selected_phrases = random.sample(chat_candidates, min(250, len(chat_candidates)))

new_chat_items = []
for phrase in selected_phrases:
    new_chat_items.append({
        "text": phrase,
        "intent": "chat",
        "entities": []
    })

final_data = existing_data + new_chat_items

with open(dataset_path, "w", encoding="utf-8") as f:
    json.dump(final_data, f, ensure_ascii=False, indent=2)

print(f"Успешно! Добавлено {len(new_chat_items)} фраз класса 'chat' в датасет.")
print(f"Всего примеров в датасете: {len(final_data)}")