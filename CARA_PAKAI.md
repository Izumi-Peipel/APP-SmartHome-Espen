# Cara Menjalankan Backend Absensi

Backend ini pakai **Express** (server) + **SQLite** (database file, tidak perlu install database terpisah).
Sudah ditest dan semua endpoint berfungsi ✅

## 1. Install Node.js (kalau belum ada)
Download dan install dari https://nodejs.org (pilih versi LTS).
Cek sudah terpasang dengan buka terminal/cmd, ketik:
```
node -v
```

## 2. Buka folder ini di terminal
```
cd attendance-backend
```

## 3. Install semua library yang dibutuhkan
```
npm install
```
(Ini akan otomatis download express, better-sqlite3, dan cors — sudah tertulis di package.json)

## 4. Jalankan server
```
node server.js
```
atau
```
npm start
```

Kalau berhasil, akan muncul tulisan:
```
✅ Server absensi jalan di:
   - http://localhost:3000
   - Cek IP LAN laptopmu (ipconfig / ifconfig) untuk dipakai di app
```

**Biarkan terminal ini tetap terbuka** selama kamu pakai aplikasinya. Kalau di-close, server mati.

## 5. Cari IP LAN laptop kamu
Supaya HP kamu (yang jalanin app Expo) bisa akses server ini, laptop dan HP harus **satu jaringan WiFi yang sama**, lalu cari IP laptop:

- **Windows**: buka cmd, ketik `ipconfig`, cari "IPv4 Address" (contoh: `192.168.1.5`)
- **Mac/Linux**: buka terminal, ketik `ifconfig` atau `ip addr`, cari alamat yang mirip `192.168.x.x`

## 6. Update alamat server di app React Native
Di file `App.js`, ubah baris:
```js
const ATTENDANCE_API = 'http://192.168.1.5:3000/attendance';
```
Ganti `192.168.1.5` dengan IP laptop kamu dari langkah 5. **Jangan pakai `localhost`**, karena itu cuma bisa diakses dari laptop itu sendiri, bukan dari HP.

## 7. Tes server dari browser (opsional, buat mastiin jalan)
Buka browser di laptop, akses:
```
http://localhost:3000/attendance
```
Kalau muncul `[]` (array kosong), berarti server sudah jalan dan siap menerima data.

## 8. Tes kirim data absen manual (opsional, pakai Postman atau curl)
```
curl -X POST http://localhost:3000/attendance -H "Content-Type: application/json" -d "{\"name\":\"Budi\"}"
```
Kalau berhasil, akan muncul response berisi data absen yang baru dibuat.

---

## Daftar Endpoint

| Method | URL                     | Fungsi                                  |
|--------|-------------------------|------------------------------------------|
| GET    | `/attendance`           | Ambil semua data absensi (terbaru dulu) |
| POST   | `/attendance`           | Tambah absen baru — body: `{ "name": "..." }` |
| DELETE | `/attendance/:id`       | Hapus satu data absensi (buat koreksi)  |

## File Database
Setelah server dijalankan pertama kali, akan otomatis muncul file `attendance.db` di folder ini.
File inilah yang menyimpan semua data absensi kamu — **jangan dihapus** kalau tidak mau kehilangan data.

## Kalau Mau Reset Data
Cukup hapus file `attendance.db`, lalu jalankan ulang server — akan dibuat database baru yang kosong.

## Troubleshooting
- **Error "port already in use"** → ada aplikasi lain yang pakai port 3000. Ganti angka `PORT` di `server.js` (misal jadi `3001`), lalu sesuaikan juga di `ATTENDANCE_API` pada app.
- **App tidak bisa connect ke server** → pastikan laptop & HP di WiFi yang sama, dan IP di `ATTENDANCE_API` sudah benar (bukan localhost).
- **Firewall memblokir** → di Windows, kadang Windows Defender minta izin saat pertama kali node.js diakses dari jaringan — klik "Allow" / "Izinkan".
