"""Warna & konstanta tampilan — palet 'Absensi Digital'.

Filosofi warna: dasar gelap netral (bukan biru pekat generik) supaya tiap
warna aksen metode absensi (RFID/Wajah/Sidik Jari) tetap menonjol dan mudah
dibedakan sekilas mata, termasuk di badge, ikon, dan progress indicator.
"""

# ---- Dasar ----
BG = "#0B0C10"            # hampir hitam, sedikit hangat (bukan navy generik)
SURFACE = "#15171D"
SURFACE_ALT = "#1E212A"
SURFACE_RAISED = "#262A35"  # untuk card yang perlu menonjol (dashboard, dialog penting)
BORDER = "#2A2E38"
BORDER_SOFT = "#20232C"

TEXT = "#F3F5F7"
TEXT_DIM = "#8D93A0"
TEXT_FAINT = "#5C6270"

# ---- Aksen utama ----
ACCENT = "#5B8CFF"         # brand utama (tombol utama, link, fokus)
ACCENT_SOFT = "#1B2540"    # background chip untuk ACCENT

# ---- Aksen per metode scan (dipakai konsisten di semua layar) ----
RFID = "#5B8CFF"           # biru — kartu RFID
RFID_SOFT = "#1B2540"
WAJAH = "#FF6FA0"          # rose — pengenalan wajah
WAJAH_SOFT = "#3A1E2C"
SIDIK = "#2FD9A8"          # teal/emerald — sidik jari
SIDIK_SOFT = "#153229"

# ---- Status ----
SUCCESS = "#2FD9A8"
DANGER = "#FF5C6C"
DANGER_SOFT = "#3A1B20"
LATE = "#FFB454"
LATE_SOFT = "#3A2A14"
KELUAR = "#C48BFF"
KELUAR_SOFT = "#2A1F3A"
INFO = "#5B8CFF"

# alias lama dipertahankan supaya file lain yang belum sempat diupdate tetap jalan
