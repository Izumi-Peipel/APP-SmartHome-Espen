"""Helper tanggal/jam & status kehadiran — port dari helper JS di App.js."""

from __future__ import annotations
from datetime import datetime, timedelta

_BULAN = [
    "Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
    "Jul", "Agu", "Sep", "Okt", "Nov", "Des",
]

JAM_MASUK_BATAS = (8, 0)  # setelah jam ini dianggap "Telat"


def to_date(scanned_at: str) -> datetime:
    """Mendukung format 'YYYY-MM-DD HH:mm:ss' maupun ISO string (dengan/atau
    tanpa offset). Sama seperti toDate() di App.js."""
    s = scanned_at.strip()
    if "T" not in s:
        s = s.replace(" ", "T")
    # buang offset timezone kalau ada, biar gampang di-parse tanpa dependency
    for sep in ("+", "Z"):
        if sep in s[10:]:
            idx = s.index(sep, 10)
            s = s[:idx]
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        # fallback paling longgar
        return datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S")


def get_status(scanned_at: str) -> str:
    """Fallback kalau backend belum kirim field 'late'."""
    try:
        d = to_date(scanned_at)
        batas_jam, batas_menit = JAM_MASUK_BATAS
        lewat = d.hour > batas_jam or (d.hour == batas_jam and d.minute > batas_menit)
        return "Telat" if lewat else "Hadir"
    except Exception:
        return "Hadir"


def format_date_time(scanned_at: str) -> tuple[str, str]:
    """Return (jam, tanggal) dengan format ala id-ID, mis. ('11:56', '29 Agu 2026')."""
    try:
        d = to_date(scanned_at)
        jam = f"{d.hour:02d}:{d.minute:02d}"
        tanggal = f"{d.day:02d} {_BULAN[d.month - 1]} {d.year}"
        return jam, tanggal
    except Exception:
        return scanned_at, ""


def is_today(scanned_at: str) -> bool:
    try:
        d = to_date(scanned_at)
        now = datetime.now()
        return d.date() == now.date()
    except Exception:
        return False


def is_this_week(scanned_at: str) -> bool:
    try:
        d = to_date(scanned_at)
        now = datetime.now()
        start_of_week = now - timedelta(days=now.weekday() + 1 if now.weekday() != 6 else 0)
        # Meniru getDay() JS (Minggu = 0): mundur ke Minggu terakhir
        days_since_sunday = (now.weekday() + 1) % 7
        start_of_week = (now - timedelta(days=days_since_sunday)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        return start_of_week <= d <= now
    except Exception:
        return False


def is_masuk_record(item: dict) -> bool:
    return item.get("type") != "pulang"


def is_late_record(item: dict) -> bool:
    late = item.get("late")
    if late is not None:
        return bool(late)
    return get_status(item.get("scanned_at", "")) == "Telat"
