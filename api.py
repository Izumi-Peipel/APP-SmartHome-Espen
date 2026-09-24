"""Klien API ke backend Express — port dari semua fetch() di App.js &
RegisterCardScreen.js, + Akun & Login.

BASE_URL:
1. Default ke DEFAULT_BASE_URL di bawah kalau belum pernah diganti.
2. Bisa diubah kapan saja dari tab Pengaturan di app -> tersimpan permanen
   lewat local_storage.py (file JSON kecil di komputer/perangkat ini).

Auth:
- Token sesi disimpan juga lewat local_storage.py, jadi user tetap login
  walau app ditutup, sampai logout manual atau sesi kedaluwarsa di server.
- set_page(page) tidak wajib lagi untuk penyimpanan (dulu dipakai untuk
  page.client_storage, yang ternyata tidak ada di versi Flet ini) --
  fungsi ini dibiarkan ada supaya main.py yang sudah memanggilnya tidak
  perlu diubah, tapi sekarang cuma menyimpan referensi page kalau-kalau
  dibutuhkan modul ini di masa depan.
- Kalau server balas 401 (sesi habis/tidak valid), semua fungsi fetch_*/
  post_*/dll di bawah otomatis memanggil unauthorized_handler yang
  didaftarkan main.py lewat set_unauthorized_handler(), supaya app bisa
  otomatis melempar user balik ke layar Login.
"""

import httpx

import local_storage

DEFAULT_BASE_URL = "https://democracy-limpness-that.ngrok-free.dev"
_STORAGE_KEY = "base_url"
_TOKEN_KEY = "auth_token"
_USERNAME_KEY = "auth_username"

_base_url = DEFAULT_BASE_URL
_token: str | None = None
_username: str | None = None
_page = None  # referensi page Flet, di-set sekali lewat set_page()
_unauthorized_handler = None  # callback async tanpa argumen, didaftarkan main.py

_TIMEOUT = 10


class AuthError(Exception):
    """Dilempar kalau server menolak request karena belum login / sesi habis."""
    pass


def set_page(page) -> None:
    """Tidak wajib lagi untuk penyimpanan (lihat docstring modul), tapi
    tetap ada supaya main.py yang sudah memanggil set_page(page) di awal
    tidak perlu diubah."""
    global _page
    _page = page


# ------------------------------------------------------------------ base url state
def get_base_url() -> str:
    """URL backend yang sedang aktif saat ini."""
    return _base_url


async def load_base_url(page=None) -> str:
    """Panggil sekali saat startup (sebelum layar lain dibangun) untuk
    memuat BASE_URL yang tersimpan dari sesi sebelumnya di perangkat ini.
    Parameter `page` dibiarkan ada (tidak dipakai) supaya pemanggilan lama
    dari main.py tidak perlu diubah."""
    global _base_url
    try:
        saved = local_storage.get(_STORAGE_KEY)
        if saved:
            _base_url = saved
    except Exception as ex:
        print("Gagal memuat BASE_URL tersimpan, pakai default:", ex)
    return _base_url


async def save_base_url(page, url: str) -> None:
    """Dipanggil dari tab Pengaturan tiap kali user ganti & simpan URL baru.
    Parameter `page` dibiarkan ada (tidak dipakai) supaya pemanggilan lama
    dari screen_settings.py tidak perlu diubah."""
    global _base_url
    _base_url = url.rstrip("/")
    try:
        local_storage.set(_STORAGE_KEY, _base_url)
    except Exception as ex:
        print("Gagal menyimpan BASE_URL ke penyimpanan lokal:", ex)


# ------------------------------------------------------------------ auth state
def get_username() -> str | None:
    return _username


def is_logged_in() -> bool:
    return _token is not None


def set_unauthorized_handler(fn) -> None:
    """main.py daftarkan callback async (tanpa argumen) di sini; dipanggil
    otomatis kalau ada request yang dibalas 401 (sesi kedaluwarsa/tidak
    valid), supaya app bisa langsung melempar user balik ke layar Login."""
    global _unauthorized_handler
    _unauthorized_handler = fn


async def load_session() -> bool:
    """Panggil sekali saat startup untuk memuat token tersimpan dari sesi
    login sebelumnya. Return True kalau ADA token tersimpan -- belum
    tentu masih valid, validasi lewat fetch_me()."""
    global _token, _username
    try:
        _token = local_storage.get(_TOKEN_KEY)
        _username = local_storage.get(_USERNAME_KEY)
    except Exception as ex:
        print("Gagal memuat sesi login tersimpan:", ex)
    return _token is not None


async def _save_session(token: str, username: str) -> None:
    global _token, _username
    _token = token
    _username = username
    try:
        local_storage.set(_TOKEN_KEY, token)
        local_storage.set(_USERNAME_KEY, username)
    except Exception as ex:
        print("Gagal menyimpan sesi login:", ex)


async def _clear_session() -> None:
    global _token, _username
    _token = None
    _username = None
    try:
        local_storage.remove(_TOKEN_KEY)
        local_storage.remove(_USERNAME_KEY)
    except Exception as ex:
        print("Gagal menghapus sesi login tersimpan:", ex)


async def force_logout() -> None:
    """Dipanggil kalau server sudah bilang sesi tidak valid (401) -- cukup
    bersihkan token lokal saja, tidak perlu memberi tahu server lagi
    (server sudah otomatis menolaknya)."""
    await _clear_session()


def _headers() -> dict:
    # ngrok-skip-browser-warning: WAJIB untuk domain *.ngrok-free.dev/.app --
    # tanpa ini, ngrok akan membalas halaman HTML "You are about to visit..."
    # (bukan JSON dari server.js) untuk semua request non-browser, yang bikin
    # r.json() gagal dengan "Expecting value: line 1 column 1 (char 0)".
    h = {"ngrok-skip-browser-warning": "true"}
    if _token:
        h["Authorization"] = f"Bearer {_token}"
    return h


async def _handle_401() -> None:
    if _unauthorized_handler is not None:
        try:
            await _unauthorized_handler()
        except Exception as ex:
            print("Gagal menjalankan unauthorized handler:", ex)


async def _request(method: str, url: str, **kwargs) -> httpx.Response:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.request(method, url, headers=_headers(), **kwargs)
    if r.status_code == 401:
        await _handle_401()
        raise AuthError("Sesi habis, silakan login lagi")
    return r


# ------------------------------------------------------------------ url builders
def attendance_url() -> str:
    return f"{_base_url}/attendance"


def attendance_summary_url() -> str:
    return f"{_base_url}/attendance/summary"


def attendance_export_url() -> str:
    # Dibuka lewat page.launch_url() (browser eksternal) -> tidak bisa kirim
    # header Authorization, jadi token dikirim lewat query param khusus
    # yang didukung requireAuth di server.
    token_part = f"?token={_token}" if _token else ""
    return f"{_base_url}/attendance/export{token_part}"


def cards_url() -> str:
    return f"{_base_url}/rfid/cards"


def last_unknown_url() -> str:
    return f"{_base_url}/rfid/last-unknown"


def backup_url() -> str:
    token_part = f"?token={_token}" if _token else ""
    return f"{_base_url}/backup/database{token_part}"


def notification_settings_url() -> str:
    return f"{_base_url}/settings/notifications"


def devices_url() -> str:
    return f"{_base_url}/devices"


def general_settings_url() -> str:
    return f"{_base_url}/settings/general"


def login_url() -> str:
    return f"{_base_url}/auth/login"


def logout_url() -> str:
    return f"{_base_url}/auth/logout"


def me_url() -> str:
    return f"{_base_url}/auth/me"


def change_password_url() -> str:
    return f"{_base_url}/auth/change-password"


# ------------------------------------------------------------------ auth calls
async def login(username: str, password: str) -> str:
    """Login, simpan token & username ke penyimpanan HP, return username
    yang berhasil login. Melempar RuntimeError dengan pesan dari server
    kalau username/password salah."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.post(
            login_url(), json={"username": username, "password": password}, headers=_headers()
        )
        try:
            data = r.json()
        except Exception:
            raise RuntimeError(
                "Server tidak membalas JSON (kemungkinan URL backend salah/mati, "
                "atau tunnel ngrok tidak aktif). Cek URL di Pengaturan."
            )
        if r.status_code >= 400:
            raise RuntimeError(data.get("error", "Login gagal"))
    await _save_session(data["token"], data["username"])
    return data["username"]


async def logout() -> None:
    try:
        await _request("POST", logout_url())
    except Exception as ex:
        print("Gagal memberi tahu server soal logout (tetap logout lokal):", ex)
    await _clear_session()


async def fetch_me() -> dict | None:
    """Validasi token tersimpan ke server. Return None kalau token tidak
    ada / sudah tidak valid lagi (otomatis membersihkan sesi lokal)."""
    if not _token:
        return None
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.get(me_url(), headers=_headers())
    if r.status_code == 401:
        await _clear_session()
        return None
    r.raise_for_status()
    return r.json()


async def change_password(current_password: str, new_password: str) -> None:
    r = await _request(
        "POST", change_password_url(),
        json={"current_password": current_password, "new_password": new_password},
    )
    data = r.json()
    if r.status_code >= 400:
        raise RuntimeError(data.get("error", "Gagal mengganti password"))


# ------------------------------------------------------------------ calls (data)
async def fetch_attendance() -> list[dict]:
    r = await _request("GET", attendance_url())
    r.raise_for_status()
    return r.json()


async def post_manual_attendance(name: str) -> dict:
    r = await _request("POST", attendance_url(), json={"name": name})
    r.raise_for_status()
    return r.json()


async def fetch_cards() -> list[dict]:
    r = await _request("GET", cards_url())
    r.raise_for_status()
    return r.json()


async def fetch_pending_card() -> dict | None:
    r = await _request("GET", last_unknown_url())
    r.raise_for_status()
    data = r.json()
    return data or None


async def register_card(uid: str, name: str) -> dict:
    r = await _request("POST", cards_url(), json={"uid": uid, "name": name})
    data = r.json()
    if r.status_code >= 400:
        raise RuntimeError(data.get("error", "Gagal mendaftarkan kartu"))
    return data


async def delete_card(uid: str) -> None:
    r = await _request("DELETE", f"{cards_url()}/{uid}")
    if r.status_code >= 400:
        raise RuntimeError("Gagal menghapus kartu")


async def fetch_notification_settings() -> dict:
    r = await _request("GET", notification_settings_url())
    r.raise_for_status()
    return r.json()


async def update_notification_settings(**kwargs) -> dict:
    """Kirim sebagian saja boleh, mis. update_notification_settings(late_attendance=False)."""
    r = await _request("PUT", notification_settings_url(), json=kwargs)
    r.raise_for_status()
    return r.json()


# ------------------------------------------------------------------ calls (devices / reader RFID)
async def fetch_devices() -> list[dict]:
    """Daftar semua reader RFID yang pernah online, dengan config-nya saat
    ini (reader_id, override broker MQTT kalau ada)."""
    r = await _request("GET", devices_url())
    r.raise_for_status()
    return r.json()


async def update_device(mac: str, **kwargs) -> dict:
    """Ubah config satu reader (reader_id/label/mqtt_host/mqtt_port/
    mqtt_user/mqtt_pass/scan_cooldown_ms/buzzer_enabled) dari app. Server
    akan menyuruh device itu reload config lewat MQTT begitu tersimpan --
    tidak perlu reflash/reboot manual. Kirim sebagian field saja boleh,
    mis. update_device(mac, reader_id="pintu_belakang")."""
    r = await _request("PUT", f"{devices_url()}/{mac}", json=kwargs)
    data = r.json()
    if r.status_code >= 400:
        raise RuntimeError(data.get("error", "Gagal memperbarui device"))
    return data


# ------------------------------------------------------------------ calls (pengaturan umum)
async def fetch_general_settings() -> dict:
    """Ambil pengaturan umum, saat ini cuma { jam_masuk_batas }."""
    r = await _request("GET", general_settings_url())
    r.raise_for_status()
    return r.json()


async def update_general_settings(**kwargs) -> dict:
    """mis. update_general_settings(jam_masuk_batas="08:30")."""
    r = await _request("PUT", general_settings_url(), json=kwargs)
    data = r.json()
    if r.status_code >= 400:
        raise RuntimeError(data.get("error", "Gagal menyimpan pengaturan umum"))
    return data