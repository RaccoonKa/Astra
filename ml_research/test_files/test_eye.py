from pathlib import Path
import cv2
import numpy as np
import onnxruntime as ort

model_path = Path("optimized_models/eye_model/eye_state_model.onnx")
if not model_path.exists():
    model_path = Path("models/eye_model/eye_state_model.onnx")

session = ort.InferenceSession(str(model_path), providers=['CPUExecutionProvider'])
input_name = session.get_inputs()[0].name
print(f"Модель загружена. Вход: {input_name}")

cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

while True:
    ret, frame = cap.read()
    if not ret or frame is None:
        continue

    h, w, _ = frame.shape
    box_size = 140
    cx, cy = w // 2, h // 2
    x1, y1 = cx - box_size // 2, cy - box_size // 2
    x2, y2 = x1 + box_size, y1 + box_size

    crop = frame[y1:y2, x1:x2]
    gray_crop = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray_crop, (32, 32), interpolation=cv2.INTER_AREA)

    blob = ((resized.astype(np.float32) / 255.0 - 0.5) / 0.5)[np.newaxis, np.newaxis, :, :]
    out = session.run(None, {input_name: blob})[0]

    raw_vals = out.flatten()
    if raw_vals.size > 1:
        pred_class = int(np.argmax(raw_vals))
    else:
        pred_class = int(raw_vals[0] >= 0.5)

    color = (0, 0, 255) if pred_class == 0 else (0, 255, 0)
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

    label = f"Class: {pred_class} | Raw: {np.round(raw_vals, 2)}"
    cv2.putText(frame, label, (x1, max(30, y1 - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    cv2.putText(frame, "Помести глаз в рамку (Q для выхода)", (20, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

    cv2.imshow("Eye Model Direct Test", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()