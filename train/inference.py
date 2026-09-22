import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from config import FINAL_MODEL_DIR, ID2EMOTION, RU_EMOTIONS

def load_predictor():
    tokenizer = AutoTokenizer.from_pretrained(str(FINAL_MODEL_DIR))
    model = AutoModelForSequenceClassification.from_pretrained(str(FINAL_MODEL_DIR))
    model.eval()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    return tokenizer, model, device

def predict(text, tokenizer, model, device, threshold=0.35):
    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=64).to(device)

    with torch.no_grad():
        outputs = model(**inputs)
        probs = torch.sigmoid(outputs.logits)[0].cpu().numpy()

    detected = []
    for idx, prob in enumerate(probs):
        if prob >= threshold:
            eng_name = ID2EMOTION[idx]
            ru_name = RU_EMOTIONS.get(eng_name, eng_name)
            detected.append((ru_name, float(prob)))

    detected.sort(key=lambda x: x[1], reverse=True)
    return detected

def interactive_session():
    print("Загрузка модели Астры...")
    tokenizer, model, device = load_predictor()
    print(f"Устройство: {device}")
    print("Пиши реплики в чат (для выхода напиши 'exit'):\n")

    while True:
        text = input("Светозар: ").strip()
        if text.lower() in ("exit", "выход", "quit"):
            break
        if not text:
            continue

        results = predict(text, tokenizer, model, device)
        if not results:
            print("Астра: нейтрально (уверенности мало)\n")
        else:
            formatted = ", ".join([f"{name} ({prob:.1%})" for name, prob in results])
            print(f"Астра почувствовала: {formatted}\n")

if __name__ == "__main__":
    interactive_session()