// ============================================================
//  BACKEND ABSENSI - Express + SQLite (+ RFID Card Registry)
//  Jalankan dengan: node server.js
// ============================================================

const express = require('express');
const cors = require('cors');
const Database = require('better-sqlite3');
const path = require('path');
const rateLimit = require('express-rate-limit');
const crypto = require('crypto'); // built-in Node -> tidak perlu npm install tambahan
const mqtt = require('mqtt');

const app = express();
const PORT = 3000; // ganti kalau port ini bentrok dengan aplikasi lain

// Jam batas masuk (format 24 jam "HH:mm"). Scan "masuk" setelah jam ini
// otomatis ditandai Terlambat. Ganti sesuai kebijakan tempat kamu.
const JAM_MASUK_BATAS = '08:00';

// ---------- Middleware ----------
app.use(cors()); // supaya app React Native boleh akses dari device lain
app.use(express.json()); // supaya bisa baca body JSON dari POST

// ---------- Rate Limiter (khusus login, cegah brute-force password) ----------
const loginLimiter = rateLimit({
  windowMs: 60 * 1000, // 1 menit
  max: 8,              // maksimal 8 percobaan login per menit per IP
  standardHeaders: true,
  legacyHeaders: false,
  message: { error: 'Terlalu banyak percobaan login, coba lagi sebentar.' },
  handler: (req, res, next, options) => {
    console.warn(`⚠️  Rate limit login terkena untuk IP ${req.ip}`);
    res.status(429).json(options.message);
  },
});

// ---------- Database ----------
const db = new Database(path.join(__dirname, 'attendance.db'));

db.exec(`
  CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    scanned_at TEXT NOT NULL
  )
`);

db.exec(`
  CREATE TABLE IF NOT EXISTS cards (
    uid TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    registered_at TEXT NOT NULL
  )
`);

// Tabel generik key-value untuk pengaturan aplikasi (dipakai oleh
// Pengaturan Notifikasi sekarang, dan bisa dipakai lagi nanti untuk
// Sensitivitas Deteksi Gerakan tanpa perlu migrasi baru).
db.exec(`
  CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
  )
`);

// ---------- Akun & Login ----------
db.exec(`
  CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
  )
`);

db.exec(`
  CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
  )
`);

const SESSION_TTL_MS = 30 * 24 * 60 * 60 * 1000; // 30 hari

// Hash password pakai scrypt bawaan Node (tidak perlu bcrypt/npm install).
// Format tersimpan: "salt:hash" (keduanya hex).
function hashPassword(password) {
  const salt = crypto.randomBytes(16).toString('hex');
  const hash = crypto.scryptSync(password, salt, 64).toString('hex');
  return `${salt}:${hash}`;
}

function verifyPassword(password, stored) {
  const [salt, hash] = stored.split(':');
  if (!salt || !hash) return false;
  const hashBuffer = Buffer.from(hash, 'hex');
  const testHash = crypto.scryptSync(password, salt, 64);
  // panjang harus sama sebelum timingSafeEqual, atau dia throw
  if (hashBuffer.length !== testHash.length) return false;
  return crypto.timingSafeEqual(hashBuffer, testHash);
}

// Bootstrap: kalau belum ada user sama sekali (instalasi baru), buat 1 akun
// admin default supaya app bisa langsung dipakai. SEGERA ganti passwordnya
// lewat menu Akun setelah login pertama kali.
(function bootstrapDefaultAdmin() {
  const count = db.prepare('SELECT COUNT(*) AS c FROM users').get().c;
  if (count === 0) {
    const defaultUsername = 'admin';
    const defaultPassword = 'admin123';
    db.prepare(
      'INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)'
    ).run(defaultUsername, hashPassword(defaultPassword), nowISOJakarta());
    console.log('============================================================');
    console.log('⚠️  Akun admin default dibuat karena belum ada user:');
    console.log(`    username: ${defaultUsername}`);
    console.log(`    password: ${defaultPassword}`);
    console.log('⚠️  SEGERA login lalu ganti password lewat menu Akun di app!');
    console.log('============================================================');
  }
})();

// Middleware: wajib login. Token bisa dikirim lewat:
//  - header  Authorization: Bearer <token>   (dipakai semua request normal)
//  - query   ?token=<token>                  (khusus endpoint yang dibuka
//    lewat page.launch_url() / browser eksternal, karena browser tidak
//    ikut mengirim header custom milik app)
function requireAuth(req, res, next) {
  const header = req.headers.authorization || '';
  let token = header.startsWith('Bearer ') ? header.slice(7) : null;
  if (!token && req.query.token) token = String(req.query.token);

  if (!token) {
    return res.status(401).json({ error: 'Butuh login' });
  }

  const session = db.prepare('SELECT * FROM sessions WHERE token = ?').get(token);
  if (!session) {
    return res.status(401).json({ error: 'Sesi tidak valid, silakan login lagi' });
  }
  if (new Date(session.expires_at).getTime() < Date.now()) {
    db.prepare('DELETE FROM sessions WHERE token = ?').run(token);
    return res.status(401).json({ error: 'Sesi kedaluwarsa, silakan login lagi' });
  }

  const user = db.prepare('SELECT id, username FROM users WHERE id = ?').get(session.user_id);
  if (!user) {
    return res.status(401).json({ error: 'Sesi tidak valid, silakan login lagi' });
  }

  req.user = user;
  req.authToken = token;
  next();
}

// ---------- Migrasi kolom baru (aman dijalankan berkali-kali) ----------
// Menambahkan kolom "type" (masuk/pulang) dan "late" (0/1) ke tabel
// attendance yang sudah ada, tanpa menghapus data lama.
function ensureColumn(table, column, definition) {
  const cols = db.prepare(`PRAGMA table_info(${table})`).all();
  const exists = cols.some((c) => c.name === column);
  if (!exists) {
    db.exec(`ALTER TABLE ${table} ADD COLUMN ${column} ${definition}`);
    console.log(`🔧 Migrasi: kolom "${column}" ditambahkan ke tabel "${table}"`);
  }
}
ensureColumn('attendance', 'type', "TEXT DEFAULT 'masuk'");
ensureColumn('attendance', 'late', 'INTEGER DEFAULT 0');

// Data lama (sebelum migrasi ini) tidak punya "type", jadi default-nya
// otomatis terisi 'masuk' oleh SQLite. Itu wajar, tidak perlu diubah manual.

// ---------- Helper: pengaturan boolean (tabel settings) ----------
function getBoolSetting(key, fallback) {
  const row = db.prepare('SELECT value FROM settings WHERE key = ?').get(key);
  if (!row) return fallback;
  return row.value === '1';
}

function setBoolSetting(key, value) {
  const v = value ? '1' : '0';
  const existing = db.prepare('SELECT key FROM settings WHERE key = ?').get(key);
  if (existing) {
    db.prepare('UPDATE settings SET value = ? WHERE key = ?').run(v, key);
  } else {
    db.prepare('INSERT INTO settings (key, value) VALUES (?, ?)').run(key, v);
  }
}

// UID kartu terakhir yang di-scan tapi BELUM terdaftar.
let lastUnknownScan = null; // { uid, scanned_at }

// ---------- Helper waktu (selalu pakai WIB / Asia/Jakarta) ----------
function getJakartaParts(dateObj = new Date()) {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Jakarta',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).formatToParts(dateObj);
  const map = {};
  parts.forEach((p) => { map[p.type] = p.value; });
  return {
    date: `${map.year}-${map.month}-${map.day}`,       // "2026-08-29"
    time: `${map.hour}:${map.minute}`,                  // "11:32" (buat cek telat)
    iso: `${map.year}-${map.month}-${map.day}T${map.hour}:${map.minute}:${map.second}+07:00`,
  };
}

function nowISOJakarta() {
  return getJakartaParts().iso;
}

// ---------- Helper: catat absen dengan logika Masuk/Pulang ----------
// Aturan:
// - Scan pertama seseorang di hari itu -> dicatat sebagai "masuk"
//   (ditandai "late" kalau jamnya lewat dari JAM_MASUK_BATAS)
// - Scan kedua di hari yang sama -> dicatat sebagai "pulang"
// - Scan ketiga dst di hari yang sama -> jam "pulang" DIPERBARUI ke waktu
//   scan terakhir (asumsinya: pulang yang "beneran" adalah tap terakhir)
function recordAttendance(name) {
  const { date, time, iso } = getJakartaParts();

  const todays = db.prepare(`
    SELECT * FROM attendance
    WHERE name = ? AND scanned_at LIKE ?
    ORDER BY scanned_at ASC
  `).all(name, `${date}%`);

  const masukRecord = todays.find((r) => r.type === 'masuk');
  const pulangRecord = todays.find((r) => r.type === 'pulang');

  if (!masukRecord) {
    const late = time > JAM_MASUK_BATAS ? 1 : 0;
    const result = db.prepare(
      'INSERT INTO attendance (name, scanned_at, type, late) VALUES (?, ?, ?, ?)'
    ).run(name, iso, 'masuk', late);
    return {
      id: result.lastInsertRowid, name, scanned_at: iso,
      type: 'masuk', late: !!late,
    };
  }

  if (!pulangRecord) {
    const result = db.prepare(
      'INSERT INTO attendance (name, scanned_at, type, late) VALUES (?, ?, ?, 0)'
    ).run(name, iso, 'pulang');

    const durasiJam = (
      (new Date(iso) - new Date(masukRecord.scanned_at)) / 3600000
    ).toFixed(2);

    return {
      id: result.lastInsertRowid, name, scanned_at: iso,
      type: 'pulang', late: false, durasi_jam: Number(durasiJam),
    };
  }

  // Sudah ada masuk & pulang hari ini -> update jam pulang ke scan terakhir
  db.prepare('UPDATE attendance SET scanned_at = ? WHERE id = ?').run(iso, pulangRecord.id);
  const durasiJam = (
    (new Date(iso) - new Date(masukRecord.scanned_at)) / 3600000
  ).toFixed(2);

  return {
    id: pulangRecord.id, name, scanned_at: iso,
    type: 'pulang', late: false, durasi_jam: Number(durasiJam), updated: true,
  };
}

// ---------- Helper: ambil data attendance dengan filter tanggal ----------
// Query params yang didukung (pilih salah satu):
//   ?date=2026-08-29            -> 1 hari spesifik
//   ?month=2026-08              -> 1 bulan penuh
//   ?from=2026-08-01&to=2026-08-07 -> rentang bebas (dipakai juga untuk "minggu")
function getFilteredAttendance({ date, month, from, to }) {
  let query = 'SELECT id, name, scanned_at, type, late FROM attendance';
  const conditions = [];
  const params = [];

  if (date) {
    conditions.push('scanned_at LIKE ?');
    params.push(`${date}%`);
  } else if (month) {
    conditions.push('scanned_at LIKE ?');
    params.push(`${month}%`);
  } else if (from && to) {
    conditions.push('substr(scanned_at, 1, 10) BETWEEN ? AND ?');
    params.push(from, to);
  }

  if (conditions.length) query += ' WHERE ' + conditions.join(' AND ');
  query += ' ORDER BY scanned_at DESC';

  const rows = db.prepare(query).all(...params);

  // Cari jam "masuk" per orang per tanggal, supaya baris "pulang" bisa
  // dilengkapi durasi_jam (dipakai di tampilan app & export CSV).
  const masukByPersonDay = {};
  rows.forEach((r) => {
    if (r.type === 'masuk') {
      const key = `${r.name}_${r.scanned_at.slice(0, 10)}`;
      masukByPersonDay[key] = r.scanned_at;
    }
  });

  return rows.map((r) => {
    const base = { ...r, late: !!r.late };
    if (r.type === 'pulang') {
      const key = `${r.name}_${r.scanned_at.slice(0, 10)}`;
      const masukTime = masukByPersonDay[key];
      if (masukTime) {
        base.durasi_jam = Number(
          ((new Date(r.scanned_at) - new Date(masukTime)) / 3600000).toFixed(2)
        );
      }
    }
    return base;
  });
}

// ============================================================
//  ROUTES - ABSENSI
// ============================================================

// GET /attendance -> daftar absen, bisa difilter:
//   /attendance?date=2026-08-29
//   /attendance?month=2026-08
//   /attendance?from=2026-08-01&to=2026-08-07
app.get('/attendance', requireAuth, (req, res) => {
  try {
    const rows = getFilteredAttendance(req.query);
    res.json(rows);
  } catch (err) {
    console.error('GET /attendance error:', err);
    res.status(500).json({ error: 'Gagal mengambil data absensi' });
  }
});

// GET /attendance/summary -> rekap jumlah masuk/pulang/terlambat per tanggal
// Bisa difilter sama seperti /attendance (date / month / from&to)
app.get('/attendance/summary', requireAuth, (req, res) => {
  try {
    const { date, month, from, to } = req.query;
    let query = `
      SELECT
        substr(scanned_at, 1, 10) AS tanggal,
        COUNT(CASE WHEN type = 'masuk' THEN 1 END) AS total_masuk,
        COUNT(CASE WHEN type = 'masuk' AND late = 1 THEN 1 END) AS total_terlambat,
        COUNT(CASE WHEN type = 'pulang' THEN 1 END) AS total_pulang
      FROM attendance
    `;
    const conditions = [];
    const params = [];

    if (date) {
      conditions.push('scanned_at LIKE ?');
      params.push(`${date}%`);
    } else if (month) {
      conditions.push('scanned_at LIKE ?');
      params.push(`${month}%`);
    } else if (from && to) {
      conditions.push('substr(scanned_at, 1, 10) BETWEEN ? AND ?');
      params.push(from, to);
    }

    if (conditions.length) query += ' WHERE ' + conditions.join(' AND ');
    query += ' GROUP BY tanggal ORDER BY tanggal DESC';

    const rows = db.prepare(query).all(...params);
    res.json(rows);
  } catch (err) {
    console.error('GET /attendance/summary error:', err);
    res.status(500).json({ error: 'Gagal mengambil rekap absensi' });
  }
});

// GET /attendance/export -> download CSV, filter sama seperti /attendance
//   /attendance/export?month=2026-08
app.get('/attendance/export', requireAuth, (req, res) => {
  try {
    const rows = getFilteredAttendance(req.query);

    let csv = 'Nama,Tanggal,Jam,Tipe,Status,Durasi (jam)\n';
    rows
      .slice()
      .sort((a, b) => a.scanned_at.localeCompare(b.scanned_at))
      .forEach((r) => {
        const tanggal = r.scanned_at.slice(0, 10);
        const jam = r.scanned_at.slice(11, 19);
        const status = r.type === 'masuk' ? (r.late ? 'Terlambat' : 'Tepat Waktu') : '-';
        const durasi = r.type === 'pulang' && r.durasi_jam != null ? r.durasi_jam.toFixed(2) : '';

        const namaAman = `"${r.name.replace(/"/g, '""')}"`;
        csv += `${namaAman},${tanggal},${jam},${r.type},${status},${durasi}\n`;
      });

    const filenameHint = req.query.date || req.query.month || 'semua';
    res.setHeader('Content-Type', 'text/csv; charset=utf-8');
    res.setHeader('Content-Disposition', `attachment; filename="absensi_${filenameHint}.csv"`);
    res.send(csv);
  } catch (err) {
    console.error('GET /attendance/export error:', err);
    res.status(500).json({ error: 'Gagal membuat file export' });
  }
});

// POST /attendance -> tombol absen manual di app (dibuatkan logika masuk/pulang juga)
app.post('/attendance', requireAuth, (req, res) => {
  try {
    const { name } = req.body;
    if (!name || typeof name !== 'string' || !name.trim()) {
      return res.status(400).json({ error: 'Field "name" wajib diisi' });
    }
    const record = recordAttendance(name.trim());
    console.log('Absen baru (manual):', record);
    res.status(201).json(record);
  } catch (err) {
    console.error('POST /attendance error:', err);
    res.status(500).json({ error: 'Gagal menyimpan data absensi' });
  }
});

app.delete('/attendance/:id', requireAuth, (req, res) => {
  try {
    const { id } = req.params;
    const result = db.prepare('DELETE FROM attendance WHERE id = ?').run(id);
    if (result.changes === 0) {
      return res.status(404).json({ error: 'Data tidak ditemukan' });
    }
    res.json({ success: true, deletedId: Number(id) });
  } catch (err) {
    console.error('DELETE /attendance error:', err);
    res.status(500).json({ error: 'Gagal menghapus data' });
  }
});

// ============================================================
//  ROUTES - RFID (kartu -> nama)
// ============================================================

// ---------- MQTT: scan RFID (menggantikan HTTP POST /rfid/scan) ----------
// Skema topic:
//   attendance/<reader_id>/scan    -> reader publish { "uid": "..." } tiap kartu ditap
//   attendance/<reader_id>/result  -> server publish balik hasilnya (buat LED/buzzer di reader)
//
// <reader_id> bebas (mis. "pintu_depan", "pintu_belakang") -- satu server
// bisa terima scan dari banyak reader sekaligus lewat wildcard subscribe.
//
// Broker & kredensial dari env var:
//   MQTT_BROKER_URL  (wajib, mis. mqtts://xxxx.emqxsl.com:8883)
//   MQTT_USERNAME, MQTT_PASSWORD (opsional, tergantung broker)

const MQTT_BROKER_URL = process.env.MQTT_BROKER_URL;
const MQTT_USERNAME = process.env.MQTT_USERNAME;
const MQTT_PASSWORD = process.env.MQTT_PASSWORD;

let mqttClient = null;

// Rate limit manual per reader_id -- gantinya express-rate-limit yang lama
// (yang cuma jalan di request HTTP), nilainya disamakan: maks 5x / 10 detik.
const SCAN_WINDOW_MS = 10 * 1000;
const SCAN_MAX_PER_WINDOW = 5;
const scanRateState = new Map(); // reader_id -> { count, windowStart }

function isScanRateLimited(readerId) {
  const now = Date.now();
  const state = scanRateState.get(readerId);
  if (!state || now - state.windowStart > SCAN_WINDOW_MS) {
    scanRateState.set(readerId, { count: 1, windowStart: now });
    return false;
  }
  state.count += 1;
  return state.count > SCAN_MAX_PER_WINDOW;
}

function parseScanTopic(topic) {
  // attendance/<reader_id>/scan
  const parts = topic.split('/');
  if (parts.length !== 3 || parts[0] !== 'attendance' || parts[2] !== 'scan') return null;
  return { readerId: parts[1] };
}

function publishScanResult(readerId, result) {
  if (!mqttClient || !mqttClient.connected) return;
  mqttClient.publish(`attendance/${readerId}/result`, JSON.stringify(result), { qos: 1 });
}

function handleScanMessage(readerId, payload) {
  const uid = typeof payload.uid === 'string' ? payload.uid.trim().toUpperCase() : null;
  if (!uid) {
    console.warn(`⚠️  Payload scan dari "${readerId}" tidak punya "uid" valid:`, payload);
    return;
  }

  if (isScanRateLimited(readerId)) {
    console.warn(`⚠️  Rate limit terkena untuk reader "${readerId}" (MQTT)`);
    publishScanResult(readerId, { ok: false, error: 'Terlalu banyak percobaan scan, coba lagi sebentar.' });
    return;
  }

  const card = db.prepare('SELECT * FROM cards WHERE uid = ?').get(uid);

  if (!card) {
    lastUnknownScan = { uid, scanned_at: nowISOJakarta() };
    console.log(`Kartu belum terdaftar (via "${readerId}"):`, uid);
    publishScanResult(readerId, { ok: false, error: 'Kartu belum terdaftar', uid });
    return;
  }

  const record = recordAttendance(card.name);
  console.log(`Absen baru (RFID via "${readerId}"):`, record);
  publishScanResult(readerId, { ok: true, ...record });
}

if (MQTT_BROKER_URL) {
  mqttClient = mqtt.connect(MQTT_BROKER_URL, {
    username: MQTT_USERNAME,
    password: MQTT_PASSWORD,
    clientId: `attendance_server_${Math.random().toString(16).slice(2, 10)}`,
    clean: true,
    reconnectPeriod: 3000,
  });

  mqttClient.on('connect', () => {
    console.log('✅ MQTT terhubung:', MQTT_BROKER_URL);
    mqttClient.subscribe('attendance/+/scan', (err) => {
      if (err) console.error('Gagal subscribe attendance/+/scan:', err.message);
      else console.log('📡 Subscribed: attendance/+/scan');
    });
  });

  mqttClient.on('reconnect', () => console.log('🔄 MQTT reconnecting...'));
  mqttClient.on('error', (err) => console.error('❌ MQTT error:', err.message));

  mqttClient.on('message', (topic, rawPayload) => {
    const parsed = parseScanTopic(topic);
    if (!parsed) return;

    let payload;
    try {
      payload = JSON.parse(rawPayload.toString());
    } catch (e) {
      console.warn('⚠️  Payload MQTT bukan JSON valid, di-skip:', topic, rawPayload.toString());
      return;
    }

    handleScanMessage(parsed.readerId, payload);
  });
} else {
  console.warn('============================================================');
  console.warn('⚠️  MQTT_BROKER_URL belum diset -- scan RFID lewat MQTT TIDAK AKTIF.');
  console.warn('   Set env var MQTT_BROKER_URL (mis. mqtts://xxxx.emqxsl.com:8883)');
  console.warn('   beserta MQTT_USERNAME / MQTT_PASSWORD kalau brokernya butuh auth.');
  console.warn('============================================================');
}

app.get('/rfid/last-unknown', requireAuth, (req, res) => {
  res.json(lastUnknownScan || null);
});

app.get('/rfid/cards', requireAuth, (req, res) => {
  try {
    const rows = db
      .prepare('SELECT uid, name, registered_at FROM cards ORDER BY registered_at DESC')
      .all();
    res.json(rows);
  } catch (err) {
    console.error('GET /rfid/cards error:', err);
    res.status(500).json({ error: 'Gagal mengambil daftar kartu' });
  }
});

app.post('/rfid/cards', requireAuth, (req, res) => {
  try {
    const { uid, name } = req.body;
    if (!uid || typeof uid !== 'string' || !uid.trim()) {
      return res.status(400).json({ error: 'Field "uid" wajib diisi' });
    }
    if (!name || typeof name !== 'string' || !name.trim()) {
      return res.status(400).json({ error: 'Field "name" wajib diisi' });
    }
    const cleanUid = uid.trim().toUpperCase();

    const existing = db.prepare('SELECT * FROM cards WHERE uid = ?').get(cleanUid);
    if (existing) {
      return res.status(409).json({ error: `Kartu ini sudah terdaftar atas nama ${existing.name}` });
    }

    const registered_at = nowISOJakarta();
    db.prepare('INSERT INTO cards (uid, name, registered_at) VALUES (?, ?, ?)').run(
      cleanUid,
      name.trim(),
      registered_at
    );

    if (lastUnknownScan && lastUnknownScan.uid === cleanUid) {
      lastUnknownScan = null;
    }

    console.log('Kartu terdaftar:', cleanUid, '->', name.trim());
    res.status(201).json({ uid: cleanUid, name: name.trim(), registered_at });
  } catch (err) {
    console.error('POST /rfid/cards error:', err);
    res.status(500).json({ error: 'Gagal mendaftarkan kartu' });
  }
});

app.delete('/rfid/cards/:uid', requireAuth, (req, res) => {
  try {
    const uid = req.params.uid.toUpperCase();
    const result = db.prepare('DELETE FROM cards WHERE uid = ?').run(uid);
    if (result.changes === 0) {
      return res.status(404).json({ error: 'Kartu tidak ditemukan' });
    }
    res.json({ success: true, deletedUid: uid });
  } catch (err) {
    console.error('DELETE /rfid/cards error:', err);
    res.status(500).json({ error: 'Gagal menghapus kartu' });
  }
});

// ============================================================
//  ROUTES - AKUN & LOGIN
// ============================================================

// POST /auth/login -> body { username, password }, balas { token, username }
app.post('/auth/login', loginLimiter, (req, res) => {
  try {
    const { username, password } = req.body || {};
    if (!username || !password) {
      return res.status(400).json({ error: 'Username & password wajib diisi' });
    }

    const user = db.prepare('SELECT * FROM users WHERE username = ?').get(username.trim());
    if (!user || !verifyPassword(password, user.password_hash)) {
      return res.status(401).json({ error: 'Username atau password salah' });
    }

    const token = crypto.randomBytes(32).toString('hex');
    const createdAt = nowISOJakarta();
    const expiresAt = new Date(Date.now() + SESSION_TTL_MS).toISOString();
    db.prepare(
      'INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)'
    ).run(token, user.id, createdAt, expiresAt);

    console.log(`Login berhasil: ${user.username}`);
    res.json({ token, username: user.username });
  } catch (err) {
    console.error('POST /auth/login error:', err);
    res.status(500).json({ error: 'Gagal memproses login' });
  }
});

// POST /auth/logout -> hapus sesi yang sedang dipakai
app.post('/auth/logout', requireAuth, (req, res) => {
  try {
    db.prepare('DELETE FROM sessions WHERE token = ?').run(req.authToken);
    res.json({ success: true });
  } catch (err) {
    console.error('POST /auth/logout error:', err);
    res.status(500).json({ error: 'Gagal logout' });
  }
});

// GET /auth/me -> validasi token tersimpan di app masih berlaku atau tidak
app.get('/auth/me', requireAuth, (req, res) => {
  res.json({ username: req.user.username });
});

// POST /auth/change-password -> body { current_password, new_password }
app.post('/auth/change-password', requireAuth, (req, res) => {
  try {
    const { current_password, new_password } = req.body || {};
    if (!current_password || !new_password) {
      return res.status(400).json({ error: 'Password lama & baru wajib diisi' });
    }
    if (new_password.length < 6) {
      return res.status(400).json({ error: 'Password baru minimal 6 karakter' });
    }

    const user = db.prepare('SELECT * FROM users WHERE id = ?').get(req.user.id);
    if (!user || !verifyPassword(current_password, user.password_hash)) {
      // PENTING: 400, bukan 401 -- kalau 401, requireAuth di sisi client
      // (api.py) akan salah mengira sesi habis dan memicu logout paksa,
      // padahal sesi user masih sah, cuma password lama yang salah ketik.
      return res.status(400).json({ error: 'Password lama salah' });
    }

    db.prepare('UPDATE users SET password_hash = ? WHERE id = ?').run(
      hashPassword(new_password),
      user.id
    );

    // Setelah ganti password, keluarkan semua sesi lain demi keamanan
    // (termasuk sesi yang lagi dipakai request ini -> app perlu login ulang).
    db.prepare('DELETE FROM sessions WHERE user_id = ?').run(user.id);

    console.log(`Password diganti untuk user: ${user.username}`);
    res.json({ success: true });
  } catch (err) {
    console.error('POST /auth/change-password error:', err);
    res.status(500).json({ error: 'Gagal mengganti password' });
  }
});

// ============================================================
//  ROUTES - PENGATURAN NOTIFIKASI
// ============================================================
// Toggle sederhana on/off untuk tiap jenis notifikasi. Disimpan di tabel
// "settings" (key-value) supaya nanti fitur lain seperti Sensitivitas
// Deteksi Gerakan bisa numpang tabel yang sama tanpa migrasi baru.

const NOTIF_DEFAULTS = {
  rfid_unknown: true,     // kartu RFID tidak dikenal discan
  late_attendance: true,  // ada yang absen "masuk" dan telat
  camera_offline: true,   // kamera jadi offline (aktif nanti setelah ESP32-CAM terpasang)
};

function getNotificationSettings() {
  return {
    rfid_unknown: getBoolSetting('notif_rfid_unknown', NOTIF_DEFAULTS.rfid_unknown),
    late_attendance: getBoolSetting('notif_late_attendance', NOTIF_DEFAULTS.late_attendance),
    camera_offline: getBoolSetting('notif_camera_offline', NOTIF_DEFAULTS.camera_offline),
  };
}

// GET /settings/notifications -> { rfid_unknown, late_attendance, camera_offline }
app.get('/settings/notifications', requireAuth, (req, res) => {
  try {
    res.json(getNotificationSettings());
  } catch (err) {
    console.error('GET /settings/notifications error:', err);
    res.status(500).json({ error: 'Gagal mengambil pengaturan notifikasi' });
  }
});

// PUT /settings/notifications -> body boleh kirim sebagian saja, mis. { "late_attendance": false }
app.put('/settings/notifications', requireAuth, (req, res) => {
  try {
    const { rfid_unknown, late_attendance, camera_offline } = req.body || {};

    if (rfid_unknown !== undefined) setBoolSetting('notif_rfid_unknown', !!rfid_unknown);
    if (late_attendance !== undefined) setBoolSetting('notif_late_attendance', !!late_attendance);
    if (camera_offline !== undefined) setBoolSetting('notif_camera_offline', !!camera_offline);

    console.log('Pengaturan notifikasi diperbarui:', getNotificationSettings());
    res.json(getNotificationSettings());
  } catch (err) {
    console.error('PUT /settings/notifications error:', err);
    res.status(500).json({ error: 'Gagal menyimpan pengaturan notifikasi' });
  }
});

app.get('/', (req, res) => {
  res.send('Server absensi aktif. Endpoint HTTP: /auth/login, /auth/logout, /auth/me, /auth/change-password, GET/POST /attendance, /attendance/summary, /attendance/export, /rfid/cards, /settings/notifications, /backup/database. Scan RFID sekarang lewat MQTT topic attendance/<reader_id>/scan (lihat MQTT_BROKER_URL).');
});

// GET /backup/database -> download file attendance.db mentah (backup penuh)
// Dipakai tombol "Penyimpanan & Backup" di app.
app.get('/backup/database', requireAuth, (req, res) => {
  try {
    const { date } = getJakartaParts();
    res.download(path.join(__dirname, 'attendance.db'), `attendance_backup_${date}.db`, (err) => {
      if (err) console.error('GET /backup/database error:', err);
    });
  } catch (err) {
    console.error('GET /backup/database error:', err);
    res.status(500).json({ error: 'Gagal membuat backup database' });
  }
});

// ============================================================
//  START SERVER
// ============================================================
app.listen(PORT, '0.0.0.0', () => {
  console.log(`✅ Server absensi jalan di:`);
  console.log(`   - http://localhost:${PORT}`);
  console.log(`   - Cek IP LAN laptopmu (ipconfig / ifconfig) untuk dipakai di app & ESP32`);
});