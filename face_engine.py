"""face_engine.py — Pengenalan wajah LOKAL pakai OpenCV DNN:
  - Deteksi wajah : YuNet  (cv2.FaceDetectorYN)
  - Pengenalan    : SFace  (cv2.FaceRecognizerSF)

Ini upgrade dari versi sebelumnya (Haar Cascade + LBPH). YuNet & SFace
adalah model resmi dari OpenCV Zoo (https://github.com/opencv/opencv_zoo),
jauh lebih akurat & tahan terhadap sudut wajah miring / pencahayaan kurang
ideal dibanding Haar Cascade, tapi TETAP ringan (total ~37MB model) dan
TETAP cuma butuh `opencv-contrib-python` -- tidak perlu install dlib/
tensorflow/pytorch yang berat & ribet compile-nya di Windows.

Semua data (embedding wajah & konfigurasi) tetap disimpan LOKAL di folder
`face_data/` -- TIDAK dikirim ke server.js maupun internet.

------------------------------------------------------------------------
PENTING -- FILE MODEL HARUS DIDOWNLOAD MANUAL SEKALI (tidak ikut ke-bundle
di kode ini karena ukurannya, dan filenya disimpan pakai Git LFS di GitHub
sehingga tidak bisa didownload otomatis lewat kode ini):

1. face_data/models/face_detection_yunet_2023mar.onnx   (~228 KB)
   https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx

2. face_data/models/face_recognition_sface_2021dec.onnx  (~37 MB)
   https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx

Kalau link di atas gagal dibuka langsung, buka halaman GitHub-nya lalu klik
tombol "Download raw file":
   https://github.com/opencv/opencv_zoo/blob/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx
   https://github.com/opencv/opencv_zoo/blob/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx

Taruh KEDUA file .onnx itu di folder face_data/models/ (buat foldernya
kalau belum ada) -- tepat di sebelah folder face_data/people/ yang sudah
ada. Tanpa file ini, is_ready() akan False dan UI akan kasih tahu user.
------------------------------------------------------------------------
"""

from __future__ import annotations

import base64
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

DATA_DIR = Path(__file__).resolve().parent / "face_data"
PEOPLE_DIR = DATA_DIR / "people"
MODELS_DIR = DATA_DIR / "models"
YUNET_MODEL_PATH = MODELS_DIR / "face_detection_yunet_2023mar.onnx"
SFACE_MODEL_PATH = MODELS_DIR / "face_recognition_sface_2021dec.onnx"
CONFIG_PATH = DATA_DIR / "config.json"
COOLDOWN_PATH = DATA_DIR / "cooldown.json"

FACE_SIZE = (200, 200)  # dipakai buat crop kecil non-alignment (blur-check, liveness)
SAMPLES_PER_PERSON = 20
MIN_SAMPLE_INTERVAL_S = 0.35  # jeda antar sampel otomatis saat enrollment
BLUR_MIN_VARIANCE = 60.0  # sampel di bawah ini dianggap terlalu buram, dilewati
LIVENESS_MIN_MOTION = 1.2  # skala 0-255; di bawah ini dicurigai foto statis/layar

# SFace mengembalikan skor KEMIRIPAN kosinus (0..1, makin BESAR makin mirip;
# rekomendasi resmi OpenCV Zoo: >0.363 dianggap orang yang sama). Supaya
# konsisten dengan kode lama (yang pakai istilah "distance", makin KECIL
# makin mirip), di sini disimpan sebagai distance = 1 - kemiripan.
# Jadi threshold makin KECIL = makin ketat (lebih sering "tidak dikenali"),
# makin BESAR = makin longgar (lebih gampang "salah kenal").
DEFAULT_MATCH_THRESHOLD = 0.65  # setara ambang kemiripan kosinus ~0.35

# Kalau ada config.json LAMA dari versi LBPH (skala beda total, biasanya
# nilainya di atas 2 misal default lama 75), nilai itu tidak relevan lagi
# di skala baru ini (0..2) -- kalau dipaksa dipakai, SEMUA wajah akan
# dianggap cocok. Nilai di atas ini dianggap "dari versi lama", direset.
_LEGACY_THRESHOLD_CUTOFF = 2.0


class FaceEngine:
    def __init__(self):
        print(f"[DEBUG] face_data path yang dipakai: {DATA_DIR.resolve()}")
        PEOPLE_DIR.mkdir(parents=True, exist_ok=True)
        MODELS_DIR.mkdir(parents=True, exist_ok=True)

        self._detector = None
        self._recognizer = None
        self._ready_error = ""

        if not YUNET_MODEL_PATH.exists() or not SFACE_MODEL_PATH.exists():
            missing = [p.name for p in (YUNET_MODEL_PATH, SFACE_MODEL_PATH) if not p.exists()]
            self._ready_error = (
                f"File model belum ada: {', '.join(missing)}. Download dulu dan taruh di "
                f"folder {MODELS_DIR}/ (lihat instruksi di komentar atas file face_engine.py)."
            )
            print(f"⚠️  {self._ready_error}")
        else:
            try:
                self._detector = cv2.FaceDetectorYN_create(
                    str(YUNET_MODEL_PATH), "", (320, 320),
                    score_threshold=0.7, nms_threshold=0.3, top_k=10,
                )
                self._recognizer = cv2.FaceRecognizerSF_create(str(SFACE_MODEL_PATH), "")
            except Exception as ex:
                self._ready_error = f"Gagal load model YuNet/SFace: {ex}"
                print(f"⚠️  {self._ready_error}")
                self._detector = None
                self._recognizer = None

        self._cap: cv2.VideoCapture | None = None
        # cache in-memory: {nama: [embedding1, embedding2, ...]} -- dibangun
        # dari file .npy tersimpan lewat train() supaya predict() tidak
        # baca disk berulang-ulang tiap frame.
        self._known: dict[str, list[np.ndarray]] = {}
        self._threshold = DEFAULT_MATCH_THRESHOLD
        self.train()
        self._load_config()

    def is_ready(self) -> bool:
        """False kalau model YuNet/SFace gagal dimuat (file belum
        didownload / instalasi opencv-contrib-python bermasalah) -- UI
        harus cek ini sebelum coba deteksi wajah."""
        return self._detector is not None and self._recognizer is not None

    def get_ready_error(self) -> str:
        """Pesan penjelasan kalau is_ready() False, buat ditampilkan ke user."""
        return self._ready_error or "Modul deteksi wajah belum siap."

    # ------------------------------------------------------------ kamera
    def open_camera(self, index: int = 0) -> bool:
        if self._cap is not None and self._cap.isOpened():
            return True
        # Di Windows, backend default (MSMF) sering LAMBAT/HANG saat pertama
        # kali membuka kamera (terutama laptop dengan kamera IR + RGB
        # sekaligus buat Windows Hello). CAP_DSHOW jauh lebih cepat & stabil
        # buat kasus ini. Di OS lain, biarkan OpenCV pilih backend default.
        if sys.platform.startswith("win"):
            self._cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        else:
            self._cap = cv2.VideoCapture(index)

        if self._cap.isOpened():
            # Batasi resolusi -- banyak webcam default ke 1280x720 atau lebih
            # tinggi, yang bikin deteksi JAUH lebih berat per frame (bisa
            # >1 detik/frame) dan kelihatan seperti "freeze". 640x480 sudah
            # lebih dari cukup buat deteksi wajah jarak dekat.
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
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

    # ------------------------------------------------------------ deteksi (YuNet)
    def detect_largest_face(self, frame):
        """Return face_row (numpy array panjang 15: x,y,w,h + 5 titik
        landmark + skor) untuk wajah terbesar di frame, atau None kalau
        tidak ada wajah terdeteksi (atau model gagal dimuat).

        CATATAN: berbeda dari versi Haar Cascade sebelumnya, return value
        di sini BUKAN tuple (x,y,w,h) polos -- selalu ambil koordinat kotak
        lewat box[:4] (bukan `x,y,w,h = box`), karena panjangnya 15, bukan 4.
        Landmark tambahan ini dipakai get_embedding() untuk alignment wajah
        (bikin SFace jauh lebih akurat dibanding crop kotak polos)."""
        if self._detector is None:
            return None
        h, w = frame.shape[:2]
        self._detector.setInputSize((w, h))
        _, faces = self._detector.detect(frame)
        if faces is None or len(faces) == 0:
            return None
        areas = faces[:, 2] * faces[:, 3]
        idx = int(np.argmax(areas))
        return faces[idx]

    def crop_face_gray(self, frame, box) -> np.ndarray:
        """Crop kotak polos (BUKAN aligned) dalam grayscale, dipakai untuk
        cek blur & liveness saja -- bukan untuk pengenalan (itu tugas
        get_embedding())."""
        x, y, w, h = [int(v) for v in box[:4]]
        x, y = max(0, x), max(0, y)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        crop = gray[y:y + h, x:x + w]
        if crop.size == 0:
            crop = np.zeros(FACE_SIZE, dtype=np.uint8)
        return cv2.resize(crop, FACE_SIZE)

    # ------------------------------------------------------------ embedding (SFace)
    def get_embedding(self, frame, box) -> np.ndarray | None:
        """Sejajarkan (align) wajah pakai 5 titik landmark dari YuNet, lalu
        ekstrak vektor fitur (embedding) 128 dimensi lewat SFace. Vektor
        inilah yang dibandingkan (bukan gambar mentah) untuk mengenali
        siapa orangnya -- jauh lebih tahan sudut wajah & pencahayaan
        dibanding cara lama (bandingkan piksel grayscale langsung)."""
        if self._recognizer is None or box is None:
            return None
        try:
            aligned = self._recognizer.alignCrop(frame, box)
            feature = self._recognizer.feature(aligned)
            return feature.flatten()
        except Exception as ex:
            print("Gagal ekstrak embedding wajah:", ex)
            return None

    # ------------------------------------------------------------ kualitas sampel & liveness
    def blur_variance(self, gray_crop: np.ndarray) -> float:
        """Skor ketajaman gambar (varians Laplacian) -- makin TINGGI makin
        tajam. Di bawah BLUR_MIN_VARIANCE dianggap terlalu buram."""
        return float(cv2.Laplacian(gray_crop, cv2.CV_64F).var())

    def is_blurry(self, gray_crop: np.ndarray) -> bool:
        return self.blur_variance(gray_crop) < BLUR_MIN_VARIANCE

    def motion_score(self, crops: list[np.ndarray]) -> float:
        """Heuristik liveness SEDERHANA: rata-rata perbedaan piksel antar
        crop wajah berurutan dalam jendela waktu singkat. Wajah asli hampir
        selalu punya sedikit gerakan mikro (kedip, napas, goyang kepala
        halus); foto yang di-print/ditunjukkan lewat layar & dipegang diam
        cenderung menghasilkan frame yang IDENTIK terus-menerus -> skor
        mendekati 0. Ini BUKAN anti-spoofing yang kuat, cuma penyaring kasus
        paling gampang (foto statis yang benar-benar tidak digerakkan)."""
        if len(crops) < 2:
            return 999.0  # belum cukup data -> jangan blokir, anggap OK
        diffs = []
        for a, b in zip(crops, crops[1:]):
            diffs.append(float(cv2.absdiff(a, b).mean()))
        return sum(diffs) / len(diffs)

    def is_likely_static(self, crops: list[np.ndarray]) -> bool:
        return self.motion_score(crops) < LIVENESS_MIN_MOTION

    # ------------------------------------------------------------ render buat Flet
    def frame_to_base64(self, frame, box=None, box_color=(91, 140, 255)) -> str:
        """Encode frame (opsional dengan kotak wajah) ke base64 JPEG,
        siap dipasang ke ft.Image(src=...)."""
        display = frame.copy()
        if box is not None:
            x, y, w, h = [int(v) for v in box[:4]]
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
        return len(list(folder.glob("*.npy")))

    def add_sample(self, name: str, embedding: np.ndarray) -> int:
        """Simpan satu embedding wajah untuk `name`. Return jumlah sampel
        yang sudah tersimpan untuk orang ini (setelah ditambah), dan
        langsung update cache in-memory supaya predict() bisa langsung
        pakai tanpa perlu train() ulang dulu."""
        folder = PEOPLE_DIR / _safe_folder(name)
        folder.mkdir(parents=True, exist_ok=True)
        idx = len(list(folder.glob("*.npy")))
        np.save(str(folder / f"{idx:03d}.npy"), embedding)
        self._known.setdefault(name, []).append(embedding)
        return idx + 1

    def list_people(self) -> list[dict]:
        """Daftar semua orang yang punya folder sampel, beserta jumlah
        sampelnya. Ini sumber data ASLI (bukan mock) untuk UI."""
        out = []
        if not PEOPLE_DIR.exists():
            return out
        for folder in sorted(PEOPLE_DIR.iterdir()):
            if folder.is_dir():
                n = len(list(folder.glob("*.npy")))
                if n > 0:
                    out.append({"name": folder.name.replace("_", " "), "samples": n})
        return out

    def delete_person(self, name: str):
        import shutil
        folder = PEOPLE_DIR / _safe_folder(name)
        if folder.exists():
            shutil.rmtree(folder)
        self.train()  # refresh cache tanpa orang ini

    # ------------------------------------------------------------ "training" & prediksi
    def train(self) -> bool:
        """SFace TIDAK perlu training seperti LBPH -- di sini fungsi ini
        cuma memuat ulang semua embedding tersimpan dari
        face_data/people/*/*.npy ke cache in-memory (self._known), supaya
        predict() cepat. Nama fungsi & cara pemanggilannya dari
        screen_face.py sengaja dipertahankan sama biar tidak perlu ubah
        banyak kode lain. Return False kalau belum ada data sama sekali."""
        known: dict[str, list[np.ndarray]] = {}
        if PEOPLE_DIR.exists():
            for folder in sorted(PEOPLE_DIR.iterdir()):
                if not folder.is_dir():
                    continue
                embeddings = []
                for f in sorted(folder.glob("*.npy")):
                    try:
                        embeddings.append(np.load(str(f)))
                    except Exception as ex:
                        print(f"Gagal load sampel {f}:", ex)
                if embeddings:
                    known[folder.name.replace("_", " ")] = embeddings

        self._known = known
        return len(known) > 0

    def has_model(self) -> bool:
        return len(self._known) > 0

    def predict(self, embedding: np.ndarray | None) -> tuple[str | None, float]:
        """Return (nama, distance) kalau cocok di bawah threshold aktif,
        atau (None, distance) kalau tidak ada yang cukup mirip / belum ada
        wajah terdaftar sama sekali. `distance` di sini = 1 - kemiripan
        kosinus tertinggi yang ditemukan (0 = identik, makin besar makin
        beda) -- lihat komentar DEFAULT_MATCH_THRESHOLD di atas file ini."""
        if embedding is None or not self.has_model() or self._recognizer is None:
            return None, 2.0

        best_name, best_distance = None, 2.0
        for name, embeddings in self._known.items():
            for known_emb in embeddings:
                similarity = self._recognizer.match(embedding, known_emb, cv2.FaceRecognizerSF_FR_COSINE)
                distance = 1.0 - float(similarity)
                if distance < best_distance:
                    best_distance = distance
                    best_name = name

        if best_name is not None and best_distance <= self._threshold:
            return best_name, best_distance
        return None, best_distance

    # ------------------------------------------------------------ konfigurasi (threshold, dsb)
    def get_threshold(self) -> float:
        return self._threshold

    def set_threshold(self, value: float):
        self._threshold = float(value)
        self._save_config()

    def _load_config(self):
        if CONFIG_PATH.exists():
            try:
                cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
                value = float(cfg.get("match_threshold", DEFAULT_MATCH_THRESHOLD))
                if value > _LEGACY_THRESHOLD_CUTOFF:
                    # ini nilai dari versi LBPH lama (skala beda total) --
                    # kalau dipakai apa adanya di skala baru (0..2), semua
                    # wajah akan dianggap cocok. Reset ke default baru.
                    print(
                        f"⚠️  Threshold tersimpan ({value}) sepertinya dari versi lama "
                        f"(LBPH), tidak relevan di skala baru ini. Direset ke default "
                        f"({DEFAULT_MATCH_THRESHOLD})."
                    )
                    self._threshold = DEFAULT_MATCH_THRESHOLD
                    self._save_config()
                else:
                    self._threshold = value
            except Exception as ex:
                print("Gagal load config wajah, pakai default:", ex)

    def reload_config(self):
        """Panggil ini kalau curiga config.json berubah dari instance
        FaceEngine lain (mis. diubah lewat dialog Pengaturan) supaya
        threshold yang dipakai selalu yang paling baru."""
        self._load_config()

    def _save_config(self):
        try:
            CONFIG_PATH.write_text(json.dumps({"match_threshold": self._threshold}), encoding="utf-8")
        except Exception as ex:
            print("Gagal menyimpan config wajah:", ex)

    # ------------------------------------------------------------ cooldown persisten (anti double-absen)
    def _load_cooldown(self) -> dict:
        if COOLDOWN_PATH.exists():
            try:
                return json.loads(COOLDOWN_PATH.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def get_last_recognized_at(self, name: str) -> float | None:
        data = self._load_cooldown()
        return data.get(name)

    def mark_recognized_now(self, name: str, timestamp: float):
        data = self._load_cooldown()
        data[name] = timestamp
        try:
            COOLDOWN_PATH.write_text(json.dumps(data), encoding="utf-8")
        except Exception as ex:
            print("Gagal menyimpan cooldown wajah:", ex)


def _safe_folder(name: str) -> str:
    return "".join(c if c.isalnum() or c in " -" else "_" for c in name).strip().replace(" ", "_") or "unnamed"