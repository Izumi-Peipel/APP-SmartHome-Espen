"""test_camera.py — Diagnostik kamera TANPA Flet sama sekali.

Jalankan langsung: python test_camera.py
(pastikan venv aktif dulu, sama seperti biasa jalankan flet run)

Tujuannya cuma satu: buktikan apakah OpenCV + kamera laptop kamu bisa buka
& baca frame tanpa hang, LEPAS dari semua kerumitan Flet/asyncio. Kalau
script ini juga freeze/hang, berarti masalahnya di kamera/driver Windows-nya
sendiri (bukan bug di kode app). Kalau script ini LANCAR tapi app Flet-nya
tetap freeze, berarti masalahnya di sisi integrasi Flet -- kabari ke saya.

Selama jalan, akan muncul window terpisah menampilkan preview kamera.
Tekan 'q' di window itu buat keluar, atau Ctrl+C di terminal.
"""

import sys
import time

import cv2

print("=" * 60)
print("STEP 1: Membuka kamera...")
print("=" * 60)
t0 = time.time()

backend = cv2.CAP_DSHOW if sys.platform.startswith("win") else 0
cap = cv2.VideoCapture(0, backend) if backend else cv2.VideoCapture(0)

print(f"Selesai coba buka kamera dalam {time.time() - t0:.2f} detik")
print(f"Status isOpened(): {cap.isOpened()}")

if not cap.isOpened():
    print("❌ GAGAL buka kamera sama sekali. Coba ganti index (0 -> 1) di baris")
    print("   'cv2.VideoCapture(0, ...)' kalau laptop kamu punya lebih dari 1 kamera,")
    print("   atau cek Windows Settings > Privacy > Camera, pastikan akses kamera")
    print("   untuk 'Desktop apps' diizinkan.")
    sys.exit(1)

cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

print()
print("=" * 60)
print("STEP 2: Membaca 5 frame pertama satu-satu (cek ada yang hang)...")
print("=" * 60)

for i in range(5):
    t0 = time.time()
    ok, frame = cap.read()
    dt = time.time() - t0
    print(f"Frame {i+1}: ok={ok}, waktu baca={dt:.3f} detik, shape={None if frame is None else frame.shape}")
    if dt > 2.0:
        print(f"  ⚠️  Frame ini butuh {dt:.1f} detik -- ini kemungkinan besar penyebab freeze!")

print()
print("=" * 60)
print("STEP 3: Live preview 10 detik (tekan 'q' di window buat keluar cepat)...")
print("=" * 60)

start = time.time()
frame_count = 0
while time.time() - start < 10:
    ok, frame = cap.read()
    if not ok:
        print("Gagal baca frame di live preview.")
        break
    frame_count += 1
    cv2.imshow("Test Kamera (tekan q buat keluar)", frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

elapsed = time.time() - start
fps = frame_count / elapsed if elapsed > 0 else 0
print(f"Selesai: {frame_count} frame dalam {elapsed:.1f} detik (~{fps:.1f} FPS)")

cap.release()
cv2.destroyAllWindows()
print()
print("✅ SELESAI TANPA HANG. Kalau sampai baris ini muncul, kamera & OpenCV kamu OK.")
