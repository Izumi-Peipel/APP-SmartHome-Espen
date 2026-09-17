"""face_engine.py — Pengenalan wajah LOKAL pakai OpenCV (Haar Cascade untuk
deteksi + LBPH untuk pengenalan). Ini implementasi SUNGGUHAN (bukan mock),
tapi sengaja pakai metode paling ringan supaya:

1. Install-nya gampang di Windows -- `opencv-contrib-python` sudah nyediakan
   prebuilt wheel, tidak perlu compiler/CMake seperti library `face_recognition`
   (yang bergantung ke dlib).
2. Semua data (foto sampel wajah & model hasil training) disimpan LOKAL di
   folder `face_data/` di komputer ini -- TIDAK dikirim ke server.js maupun
   internet. Kalau nanti pindah komputer, folder ini harus disalin manual.

Akurasi LBPH lebih rendah dibanding model deep-learning modern, tapi cukup
untuk prototipe/"sementara" dengan jumlah orang terdaftar tidak terlalu
banyak & kondisi pencahayaan konsisten. Threshold confidence bisa disetel
lewat MATCH_THRESHOLD di bawah kalau ternyata kebanyakan salah kenal /
kebanyakan menolak.
"""

from __future__ import annotations

import base64
import json
import time
from pathlib import Path

import cv2
import numpy as np

DATA_DIR = Path("face_data")
PEOPLE_DIR = DATA_DIR / "people"
MODEL_PATH = DATA_DIR / "model.yml"
LABELS_PATH = DATA_DIR / "labels.json"

FACE_SIZE = (200, 200)  # semua crop wajah diseragamkan ke ukuran ini
SAMPLES_PER_PERSON = 20
MIN_SAMPLE_INTERVAL_S = 0.35  # jeda antar sampel otomatis saat enrollment

# LBPH predict() mengembalikan "distance" (BUKAN persentase kemiripan) --
# semakin KECIL semakin mirip. 0 = identik, biasanya di atas ~90-100 sudah
# dianggap orang berbeda. Nilai ini sering perlu disesuaikan per kondisi
# kamera/pencahayaan kamu.
MATCH_THRESHOLD = 75


class FaceEngine:
    def __init__(self):
        PEOPLE_DIR.mkdir(parents=True, exist_ok=True)
        self._cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        self._cap: cv2.VideoCapture | None = None
        self._recognizer = None  # dibuat lazy, cuma kalau cv2.face tersedia
        self._labels: dict[int, str] = {}  # label numerik -> nama
        self._load_model_if_exists()

    # ------------------------------------------------------------ kamera
    def open_camera(self, index: int = 0) -> bool:
        if self._cap is not None and self._cap.isOpened():
            return True
        self._cap = cv2.VideoCapture(index)
        return self._cap.isOpened()

    def close_camera(self):
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def is_camera_open(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    def read_frame(self):
        """BLOCKING -- panggil lewat asyncio.to_thread() dari kode Flet.
        Return frame BGR (numpy array) atau None kalau gagal baca."""
        if not self.is_camera_open():
            return None
        ok, frame = self._cap.read()
        if not ok:
            return None
        return cv2.flip(frame, 1)  # mirror, lebih natural buat user

    # ------------------------------------------------------------ deteksi
    def detect_largest_face(self, frame):
        """Return (x, y, w, h) wajah terbesar di frame, atau None kalau
        tidak ada wajah terdeteksi."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self._cascade.detectMultiScale(gray, scaleFactor=1.15, minNeighbors=5, minSize=(80, 80))
        if len(faces) == 0:
            return None
        # ambil yang terbesar (area w*h) -- asumsinya itu wajah paling
        # dekat ke kamera / paling relevan
        x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
        return int(x), int(y), int(w), int(h)

    def crop_face_gray(self, frame, box) -> np.ndarray:
        x, y, w, h = box
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        crop = gray[y:y + h, x:x + w]
        return cv2.resize(crop, FACE_SIZE)

    # ------------------------------------------------------------ render buat Flet
    def frame_to_base64(self, frame, box=None, box_color=(91, 140, 255)) -> str:
        """Encode frame (opsional dengan kotak wajah) ke base64 JPEG,
        siap dipasang ke ft.Image(src_base64=...)."""
        display = frame.copy()
        if box is not None:
            x, y, w, h = box
            cv2.rectangle(display, (x, y), (x + w, y + h), box_color, 2)
        ok, buf = cv2.imencode(".jpg", display, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not ok:
            return ""
        return base64.b64encode(buf).decode("ascii")

    # ------------------------------------------------------------ enrollment
    def sample_count(self, name: str) -> int:
        folder = PEOPLE_DIR / _safe_folder(name)
        if not folder.exists():
            return 0
        return len(list(folder.glob("*.png")))

    def add_sample(self, name: str, gray_crop: np.ndarray) -> int:
        """Simpan satu sampel wajah untuk `name`. Return jumlah sampel
        yang sudah tersimpan untuk orang ini (setelah ditambah)."""
        folder = PEOPLE_DIR / _safe_folder(name)
        folder.mkdir(parents=True, exist_ok=True)
        idx = len(list(folder.glob("*.png")))
        cv2.imwrite(str(folder / f"{idx:03d}.png"), gray_crop)
        return idx + 1

    def list_people(self) -> list[dict]:
        """Daftar semua orang yang punya folder sampel, beserta jumlah
        sampelnya. Ini sumber data ASLI (bukan mock) untuk UI."""
        out = []
        if not PEOPLE_DIR.exists():
            return out
        for folder in sorted(PEOPLE_DIR.iterdir()):
            if folder.is_dir():
                n = len(list(folder.glob("*.png")))
                if n > 0:
                    out.append({"name": folder.name.replace("_", " "), "samples": n})
        return out

    def delete_person(self, name: str):
        import shutil
        folder = PEOPLE_DIR / _safe_folder(name)
        if folder.exists():
            shutil.rmtree(folder)
        self.train()  # retrain tanpa orang ini

    # ------------------------------------------------------------ training & prediksi
    def train(self) -> bool:
        """Latih ulang model LBPH dari semua sampel di face_data/people/.
        Return False kalau data belum cukup (butuh minimal 1 orang)."""
        images, labels = [], []
        label_map: dict[int, str] = {}
        next_label = 0

        for folder in sorted(PEOPLE_DIR.iterdir()) if PEOPLE_DIR.exists() else []:
            if not folder.is_dir():
                continue
            samples = list(folder.glob("*.png"))
            if not samples:
                continue
            label_map[next_label] = folder.name.replace("_", " ")
            for f in samples:
                img = cv2.imread(str(f), cv2.IMREAD_GRAYSCALE)
                if img is not None:
                    images.append(img)
                    labels.append(next_label)
            next_label += 1

        if not images:
            return False

        recognizer = cv2.face.LBPHFaceRecognizer_create()
        recognizer.train(images, np.array(labels))
        recognizer.save(str(MODEL_PATH))
        LABELS_PATH.write_text(json.dumps(label_map), encoding="utf-8")

        self._recognizer = recognizer
        self._labels = label_map
        return True

    def _load_model_if_exists(self):
        if MODEL_PATH.exists() and LABELS_PATH.exists():
            try:
                recognizer = cv2.face.LBPHFaceRecognizer_create()
                recognizer.read(str(MODEL_PATH))
                self._recognizer = recognizer
                self._labels = {int(k): v for k, v in json.loads(LABELS_PATH.read_text(encoding="utf-8")).items()}
            except Exception as ex:
                print("Gagal load model wajah tersimpan (perlu training ulang):", ex)

    def has_model(self) -> bool:
        return self._recognizer is not None and len(self._labels) > 0

    def predict(self, gray_crop: np.ndarray) -> tuple[str | None, float]:
        """Return (nama, distance) kalau cocok di bawah MATCH_THRESHOLD,
        atau (None, distance) kalau tidak ada yang cukup mirip / model
        belum ada sama sekali."""
        if not self.has_model():
            return None, 999.0
        label, distance = self._recognizer.predict(gray_crop)
        if distance <= MATCH_THRESHOLD and label in self._labels:
            return self._labels[label], float(distance)
        return None, float(distance)


def _safe_folder(name: str) -> str:
    return "".join(c if c.isalnum() or c in " -" else "_" for c in name).strip().replace(" ", "_") or "unnamed"
