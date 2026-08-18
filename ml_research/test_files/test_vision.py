import sys
import cv2
from PyQt6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget
from PyQt6.QtGui import QImage, QPixmap
from core.vision.vision_provider import VisionThread


class CameraTestWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Тест зрения Астры")
        self.resize(640, 480)

        self.label = QLabel("Подключение к веб-камере...")
        layout = QVBoxLayout()
        layout.addWidget(self.label)
        self.setLayout(layout)

        self.vision_thread = VisionThread(camera_index=0)
        self.vision_thread.frame_processed.connect(self.display_frame)
        self.vision_thread.face_detected_signal.connect(self.on_face_detected)
        self.vision_thread.start()

    def display_frame(self, frame):
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_frame.shape
        bytes_per_line = ch * w
        q_img = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        self.label.setPixmap(QPixmap.fromImage(q_img))

    def on_face_detected(self, has_face):
        status = "Вижу лицо!" if has_face else "Лицо не найдено"
        print(f"[VISION STATUS]: {status}")

    def closeEvent(self, event):
        self.vision_thread.stop()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CameraTestWindow()
    window.show()
    sys.exit(app.exec())