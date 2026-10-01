# Absensi Digital — Flet (Python) + Express/MQTT + ESP32

Sistem absensi dengan **kartu RFID**. Pembaca kartu (ESP32 + RC522) mengirim
UID ke backend lewat MQTT, backend mencatat absen, lalu aplikasi Flet menampilkan
dan mengelola datanya. Pengaturan perangkat (Reader ID, broker MQTT, jeda
scan, buzzer, LED) diubah dari aplikasi **tanpa upload ulang firmware**.

> Status metode scan: **RFID** aktif penuh. Menu Wajah sudah dihapus. **Sidik
> Jari** hanya placeholder di Pengaturan (belum ada sensor/integrasinya).

## Cara kerja

```
 ESP32 + RC522 ──MQTT──►  Broker MQTT  ◄──MQTT──  Backend (Express + SQLite)
   (firmware .ino)                                        ▲
        ▲                                                 │ HTTP
        └──── GET /devices/<MAC> (ambil config) ──────────┤
                                                          │
                                                   Aplikasi Flet
```

1. Kartu ditempel → ESP32 publish ke `attendance/<reader_id>/scan`.
2. Backend mencatat absen lalu membalas ke `attendance/<reader_id>/result`.
3. ESP32 menampilkan hasil di LCD, membunyikan buzzer, dan menyalakan LED
   (hijau = berhasil, merah = ditolak).
4. Saat pengaturan perangkat disimpan di aplikasi, backend mengirim
   `config/<mac>/reload`; ESP32 restart dan mengambil config terbaru.

## Tab aplikasi

- **Beranda** — ringkasan absensi hari ini
- **Absensi** — riwayat lengkap, statistik, pencarian, filter tanggal, absen
  manual, detail riwayat per orang
- **Scan** — RFID: daftarkan kartu baru (polling kartu yang belum dikenal),
  ubah nama kartu, hapus kartu
- **Pengaturan**
  - Pengaturan Notifikasi
  - Jam Kerja & Keterlambatan
  - **Kelola Perangkat RFID** — per perangkat: Reader ID, Broker MQTT & port,
    jeda anti-scan-ganda (ms), saklar **Buzzer**, saklar **LED merah/hijau**
  - Kelola Data Sidik Jari (placeholder)
  - Penyimpanan & Backup — backup database (`.db`) dan export laporan (`.csv`)
  - Akun (ganti password) dan Keluar

## Struktur proyek

```
main.py                 # entrypoint, NavigationBar
theme.py                # palet warna
utils.py                # helper tanggal/jam/status
api.py                  # semua pemanggilan backend (httpx async)
screen_home.py          # tab Beranda
screen_attendance.py    # tab Absensi
screen_scan.py          # tab Scan
screen_cards.py         # komponen kartu RFID
screen_settings.py      # tab Pengaturan (termasuk Kelola Perangkat RFID)
screen_login.py         # layar login
local_storage.py        # penyimpanan lokal kecil (base_url, token sesi)

backend/
  server.js             # Express + SQLite + klien MQTT
  package.json

rfid_attendance.ino     # firmware ESP32 (di Arduino IDE simpan di folder
                        # bernama "rfid_attendance")
```

## Aplikasi (Flet)

Ditulis dan diverifikasi untuk **Flet 0.86.x** (`ft.run()`,
`page.show_dialog()` / `page.pop_dialog()`, `ft.Icons.NAMA_ICON` huruf besar).
Kalau versi Flet jauh lebih lama: `pip install --upgrade flet`.

```bash
pip install -r requirements.txt
flet run main.py            # desktop / dev
flet run --web main.py      # web, untuk testing cepat
flet build apk              # build APK Android
```

Mencoba di HP tanpa build APK: install app **Flet**, jalankan
`flet run main.py`, lalu scan QR code di terminal.

URL backend diatur lewat `DEFAULT_BASE_URL` di `api.py`, atau dari
**Pengaturan → URL Backend** di aplikasi (tersimpan di perangkat, tidak perlu
build ulang).

## Backend

```bash
cd backend
npm install
node server.js
```

### Environment variable

| Variable | Fungsi |
|---|---|
| `PORT` | Port HTTP (default 3000; Railway mengisinya otomatis) |
| `MQTT_BROKER_URL` | Alamat broker, mis. `mqtts://xxxx.emqxsl.com:8883`. Tanpa ini scan RFID tidak aktif |
| `MQTT_USERNAME` / `MQTT_PASSWORD` | Kredensial broker |
| `DEVICE_PROVISION_KEY` | Kunci rahasia untuk `GET /devices/:mac`; **harus sama** dengan `DEVICE_KEY` di firmware |
| `DATA_DIR` | Folder penyimpanan `attendance.db` (default: folder `server.js`) |
| `ADMIN_INITIAL_USERNAME` / `ADMIN_INITIAL_PASSWORD` | Akun admin awal |

> **Penting di Railway:** tanpa Volume, file database ikut hilang setiap deploy
> ulang. Buat Volume, mount ke satu path (mis. `/data`), lalu set
> `DATA_DIR=/data`. Rutin gunakan Backup Database dari aplikasi.

### Deploy ke Railway

- Repo berisi backend di folder `backend/`, jadi di Railway buka **Settings →
  Root Directory** dan isi `/backend`. Tanpa ini deploy gagal ("Deployment
  failed") karena `package.json` tidak ditemukan.
- Pastikan `backend/package.json` punya script `"start": "node server.js"`.
- Pastikan `.gitignore` berisi `node_modules/`.

### Endpoint

| Endpoint | Keterangan |
|---|---|
| `POST /auth/login`, `/auth/logout`, `/auth/change-password`; `GET /auth/me` | Autentikasi |
| `GET/POST /attendance`, `DELETE /attendance/:id` | Riwayat & absen manual |
| `GET /attendance/summary`, `/attendance/export` | Ringkasan & export CSV |
| `GET/POST /rfid/cards`, `PUT/DELETE /rfid/cards/:uid` | Kartu RFID (PUT = ubah nama) |
| `GET /rfid/last-unknown` | Kartu terakhir yang belum terdaftar |
| `GET /devices/:mac` | Dipanggil firmware (tanpa login, pakai `?key=`) |
| `GET /devices`, `PUT /devices/:mac` | Daftar & pengaturan perangkat dari aplikasi |
| `GET/PUT /settings/notifications`, `/settings/general` | Notifikasi, jam kerja |
| `GET /backup/database` | Unduh database |

Field perangkat di `PUT /devices/:mac`: `reader_id`, `label`, `mqtt_host`,
`mqtt_port`, `mqtt_user`, `mqtt_pass`, `scan_cooldown_ms`, `buzzer_enabled`,
`led_enabled`. Kolom baru dibuat otomatis lewat migrasi saat server start.

## Firmware ESP32 (`rfid_attendance.ino`)

Library (Arduino IDE → Library Manager): **WiFiManager** (tzapu),
**ArduinoJson**, **PubSubClient** (Nick O'Leary), **MFRC522**,
**LiquidCrystal_I2C**. `Preferences` dan `HTTPClient` sudah bawaan core ESP32.

Sebelum upload, ubah dua konstanta di bagian atas file:

- `DEVICE_KEY` — samakan dengan `DEVICE_PROVISION_KEY` di server.
- `AP_SETUP_PASSWORD` — password WiFi setup (minimal 8 karakter). Jangan
  dibiarkan default.

### Setup pertama per perangkat

1. Nyalakan ESP32. Muncul WiFi bernama **RFID-Setup** (password sesuai
   `AP_SETUP_PASSWORD`; tampil juga di LCD).
2. Sambungkan HP/laptop, buka halaman yang muncul, isi WiFi dan **URL Server**.
   Cukup sekali.
3. Perangkat mengambil config dari server dan otomatis terdaftar. Beri nama dan
   atur dari **Pengaturan → Kelola Perangkat RFID**.

Mengulang setup WiFi: setelah LCD menampilkan `READY TO SCAN`, **tahan tombol
BOOT 3 detik**. (Jangan menahan BOOT saat menyalakan; GPIO0 akan membuat chip
masuk mode flashing.)

### Pin

| Fungsi | GPIO |
|---|---|
| RC522 SDA / RST | 21 / 22 |
| RC522 SCK / MOSI / MISO | 18 / 23 / 19 |
| LED hijau / LED merah | 4 / 5 |
| Buzzer | 12 |
| LCD I2C SDA / SCL | 13 / 14 (alamat 0x27) |

### Perilaku

- Config terakhir yang berhasil diambil disimpan di memori perangkat, jadi
  perangkat tetap jalan kalau server sedang tidak terjangkau saat boot.
- Saklar **Buzzer** dan **LED** dari aplikasi berlaku setelah perangkat
  restart otomatis. LED menyala selama pesan hasil scan tampil di LCD.
- Anti-hang: WiFi sleep dimatikan, keepalive MQTT 30 detik, dan watchdog RC522
  yang menginisialisasi ulang modul bila tidak merespons.

## Troubleshooting

- **Tanda ✗ merah di commit GitHub** — itu hasil deploy Railway. Cek tab
  Deployments; kalau deploy terbaru *Active*, tanda merah di commit lama bisa
  diabaikan. Penyebab umum: Root Directory belum `/backend`.
- **Scan berhenti setelah beberapa menit** — buka Serial Monitor lalu tempelkan
  kartu. Tidak ada "Kartu terbaca" berarti RC522 hang (periksa kabel jumper
  pendek dan catu 3.3V stabil). Ada "Kartu terbaca" tapi absen tidak masuk
  berarti cek koneksi MQTT dan log Railway.
- **Saklar buzzer/LED tidak berpengaruh** — pastikan firmware terbaru sudah
  terupload dan server terbaru sudah ter-deploy; `GET /devices/<MAC>?key=...`
  harus memuat `buzzer_enabled` dan `led_enabled`.
- **Kartu yang sama ditempel berulang tidak bereaksi** — itu jeda
  anti-scan-ganda (default 3000 ms), bisa diubah di Kelola Perangkat RFID.