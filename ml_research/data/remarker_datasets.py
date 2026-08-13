import json

with open("intents_slot_fillings.json", "r", encoding="utf-8") as f:
  data = json.load(f)

for item in data:
  text = item["text"]
  for ent in item["entities"]:
    val = ent["value"]
    start = text.find(val)
    if start != -1:
      ent["start"] = start
      ent["end"] = start + len(val)

with open("intents_slot_fillings_fixed.json", "w", encoding="utf-8") as f:
  json.dump(data, f, ensure_ascii=False, indent=2)