# CCTV App Espen — versi Flet (Python)

Port dari `cctv-app5` (Expo/React Native) ke [Flet](https://flet.dev), dijalankan
dengan Python murni, tetap bisa jadi app Android/iOS beneran.

## Fitur (sama seperti versi RN)

- **Live** — daftar kamera + placeholder video (masih mock, belum konek ESP32-CAM)
- **Riwayat** — daftar rekaman (masih mock)
- **Absensi** — fetch ke backend tiap 15 detik, statistik hadir/telat/minggu ini,
  pencarian nama, filter tanggal (hari ini/minggu ini/semua/tanggal spesifik),
  absen manual, detail riwayat per orang
- **Kartu RFID** — polling kartu baru yang belum terdaftar tiap 3 detik,
  daftarkan kartu, hapus kartu
- **Pengaturan** — backup database (.db) & export laporan (.csv), buka lewat browser/URL launcher

## Menjalankan di komputer (mode desktop/dev)

```bash
pip install -r requirements.txt
flet run main.py
```

Ini akan membuka window desktop. Kalau mau lihat di browser dulu untuk testing cepat:

```bash
flet run --web main.py
```

## Menjalankan di HP tanpa build APK (mode Flet App / hot reload)

1. Install app **Flet** dari Play Store / App Store di HP kamu.
2. Di komputer, jalankan:
   ```bash
   flet run main.py
   ```
3. Scan QR code yang muncul di terminal pakai app Flet di HP — mirip alur Expo Go.

## Build jadi APK Android beneran

```bash
flet build apk
```

File `.apk` hasilnya ada di folder `build/apk/`. (Butuh Flutter SDK ter-install;
`flet build` akan kasih tahu kalau ada yang kurang.)

## Konfigurasi backend

Buka `api.py`, ganti baris ini sesuai domain ngrok/backend kamu (harus 1 domain
yang sama dengan sebelumnya dipakai di App.js):

```python
BASE_URL = "https://democracy-limpness-that.ngrok-free.dev"
```

Endpoint yang dipakai (harus sudah ada di backend FastAPI kamu):

| Method | Path | Keterangan |
|---|---|---|
| GET | `/attendance` | daftar absensi |
| POST | `/attendance` | absen manual, body `{ "name": "..." }` |
| GET | `/rfid/cards` | daftar kartu terdaftar |
| POST | `/rfid/cards` | daftarkan kartu, body `{ "uid": "...", "name": "..." }` |
| DELETE | `/rfid/cards/{uid}` | hapus kartu |
| GET | `/rfid/last-unknown` | kartu baru yang belum terdaftar (atau `null`) |
| GET | `/backup/database` | download file `.db` |
| GET | `/attendance/export` | download laporan `.csv` |

## Struktur file

```
main.py              # entrypoint, NavigationBar 5 tab
theme.py              # palet warna (sama dengan COLORS di App.js)
utils.py              # helper tanggal/jam/status (port toDate, getStatus, dst.)
api.py                # semua pemanggilan backend (httpx async)
screens_static.py     # tab Live & Riwayat (mock)
screen_attendance.py  # tab Absensi (fetch real + polling + filter + modal)
screen_cards.py        # tab Kartu RFID (fetch real + polling + register/delete)
screen_settings.py    # tab Pengaturan (backup & export)
```

## Catatan versi Flet

Kode ini ditulis & diverifikasi untuk **Flet 0.86.x**, yaitu API terbaru
(`ft.run()`, `page.show_dialog()`/`page.pop_dialog()`, `ft.Icons.NAMA_ICON`
huruf besar semua, dst). Kalau `pip install flet` di komputer kamu menarik
versi jauh lebih lama (< 0.70-an), beberapa nama fungsi bisa beda — tinggal
`pip install --upgrade flet` untuk menyamakan.
