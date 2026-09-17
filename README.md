# Absensi Digital — versi Flet (Python)

Aplikasi absensi dengan 3 metode scan: **RFID** (aktif & berfungsi penuh lewat
backend Express + MQTT), **Wajah**, dan **Sidik Jari** (dua yang terakhir
masih **mode simulasi/mockup** — UI sudah jadi, tinggal disambungkan ke
model face-recognition & sensor fisik nanti).

## Tab Navigasi

- **Beranda** — dashboard ringkasan absensi hari ini + pintasan ke 3 metode scan
- **Absensi** — riwayat lengkap, statistik hadir/telat/minggu ini, pencarian,
  filter tanggal, absen manual, detail riwayat per orang
- **Scan** — hub 3 metode: RFID (pendaftaran & polling kartu baru real-time),
  Wajah (simulasi deteksi + daftar contoh), Sidik Jari (simulasi + daftar contoh)
- **Pengaturan** — notifikasi, kelola data wajah/sidik jari (placeholder),
  backup database (.db) & export laporan (.csv), akun, logout

## Menjalankan di komputer (mode desktop/dev)

```bash
pip install -r requirements.txt
flet run main.py
```

Mode web untuk testing cepat:

```bash
flet run --web main.py
```

## Menjalankan di HP tanpa build APK

1. Install app **Flet** dari Play Store / App Store.
2. Di komputer: `flet run main.py`
3. Scan QR code yang muncul di terminal.

## Build jadi APK Android

```bash
flet build apk
```

## Konfigurasi backend

Ganti `DEFAULT_BASE_URL` di `api.py`, atau langsung dari tab **Pengaturan > URL
Backend** di dalam app (tersimpan permanen di HP, tidak perlu build ulang APK).

## Struktur file

```
main.py               # entrypoint, NavigationBar 4 tab
theme.py               # palet warna "Absensi Digital" — 1 aksen per metode scan
utils.py               # helper tanggal/jam/status
api.py                 # semua pemanggilan backend (httpx async)
screen_home.py         # tab Beranda — dashboard ringkasan
screen_attendance.py   # tab Absensi (fetch real + polling + filter + modal)
screen_scan.py          # tab Scan — hub RFID / Wajah* / Sidik Jari*
screen_cards.py         # komponen RFID (dipakai embedded di screen_scan.py)
screen_settings.py     # tab Pengaturan
screen_login.py        # layar login
local_storage.py       # penyimpanan lokal kecil (base_url, token sesi)
```

*Wajah & Sidik Jari: lihat badge "Mode Simulasi" di layar Scan — belum
terhubung ke hardware/model asli, murni contoh interaksi & tampilan.*

## Catatan versi Flet

Ditulis & diverifikasi untuk **Flet 0.86.x** (`ft.run()`, `page.show_dialog()`
/`page.pop_dialog()`, `ft.Icons.NAMA_ICON` huruf besar semua). Kalau versi
Flet kamu jauh lebih lama, jalankan `pip install --upgrade flet`.
