"""local_storage.py - penyimpanan kecil berbasis file JSON di disk lokal.

Dibuat sebagai pengganti page.client_storage, yang ternyata TIDAK ADA di
versi Flet yang ke-install ('Page' object has no attribute
'client_storage'). API client_storage/session_storage memang beberapa
kali berubah nama & lokasi antar versi Flet, jadi daripada menebak nama
yang benar untuk versi kamu, modul ini menyimpan sendiri ke sebuah file
JSON kecil -- tidak bergantung pada Flet sama sekali, jadi tidak akan
rusak lagi walau Flet di-update ke versi lain nanti.

Dipakai untuk menyimpan: BASE_URL backend, token sesi login, & username --
supaya semuanya tetap ada walau app ditutup dan dibuka lagi.

Catatan: ini penyimpanan lokal di perangkat/komputer tempat app berjalan
(folder home user), sama seperti fungsi client_storage yang aslinya mau
dipakai -- bukan dikirim ke server.
"""

import json
import os
from pathlib import Path

_APP_DIR_NAME = "cctv_app_espen"
_FILE_NAME = "local_storage.json"


def _storage_dir() -> Path:
    """Folder tempat file storage disimpan, disesuaikan per OS supaya
    selalu ada izin tulis:
    - Windows: %APPDATA%
    - Linux/Mac: $XDG_CONFIG_HOME atau ~/.config
    - fallback terakhir: folder home user langsung
    """
    base = os.environ.get("APPDATA") or os.environ.get("XDG_CONFIG_HOME")
    if not base:
        base = str(Path.home() / ".config")
    path = Path(base) / _APP_DIR_NAME
    try:
        path.mkdir(parents=True, exist_ok=True)
    except Exception as ex:
        print("Gagal membuat folder storage, pakai folder home:", ex)
        path = Path.home()
    return path


def _storage_file() -> Path:
    return _storage_dir() / _FILE_NAME


def _read_all() -> dict:
    file = _storage_file()
    if not file.exists():
        return {}
    try:
        return json.loads(file.read_text(encoding="utf-8"))
    except Exception as ex:
        print("Gagal membaca storage lokal (mulai dari kosong):", ex)
        return {}


def _write_all(data: dict) -> None:
    file = _storage_file()
    try:
        file.write_text(json.dumps(data), encoding="utf-8")
    except Exception as ex:
        print("Gagal menulis storage lokal:", ex)


def get(key: str) -> str | None:
    """Ambil satu nilai tersimpan. Return None kalau belum pernah diset."""
    return _read_all().get(key)


def set(key: str, value: str) -> None:
    """Simpan satu nilai (menimpa kalau sudah ada key yang sama)."""
    data = _read_all()
    data[key] = value
    _write_all(data)


def remove(key: str) -> None:
    """Hapus satu nilai tersimpan. Aman dipanggil walau key tidak ada."""
    data = _read_all()
    if key in data:
        del data[key]
        _write_all(data)
