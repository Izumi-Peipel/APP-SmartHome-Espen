"""HomeView — dashboard Beranda. Menggantikan tab 'Live' (CCTV) lama.
Menampilkan ringkasan absensi hari ini, jam saat ini, dan pintasan ke tiga
metode scan (RFID / Wajah / Sidik Jari)."""

import asyncio
from datetime import datetime
import flet as ft
import theme as C
import api
from utils import is_today, is_this_week, is_masuk_record, is_late_record, format_date_time

REFRESH_INTERVAL_S = 20

_HARI = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
_BULAN = [
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
]


def _today_str() -> str:
    now = datetime.now()
    return f"{_HARI[now.weekday()]}, {now.day} {_BULAN[now.month - 1]} {now.year}"


class HomeView:
    def __init__(self, page: ft.Page, on_go_scan=None):
        self.page = page
        self.on_go_scan = on_go_scan  # callback(method:str|None) -> pindah tab Scan
        self._running = False
        self.attendance: list[dict] = []

        # ---- header ----
        self.greeting_text = ft.Text(self._greeting(), size=13, color=C.TEXT_DIM)
        self.date_text = ft.Text(_today_str(), size=20, weight=ft.FontWeight.BOLD, color=C.TEXT)
        username = api.get_username() or "Admin"
        avatar = ft.Container(
            content=ft.Text(username[:1].upper(), color=C.BG, weight=ft.FontWeight.BOLD, size=16),
            width=40, height=40, border_radius=ft.BorderRadius.all(20),
            bgcolor=C.ACCENT, alignment=ft.Alignment.CENTER,
        )
        header = ft.Row(
            [
                ft.Column([self.greeting_text, self.date_text], spacing=2, expand=True),
                avatar,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        # ---- kartu ringkasan besar ----
        self.big_hadir = ft.Text("0", size=32, weight=ft.FontWeight.BOLD, color=C.TEXT)
        self.big_sub = ft.Text("orang sudah absen hari ini", size=12, color=C.TEXT_DIM)
        self.ring_telat = ft.Text("0 telat", size=12, color=C.LATE, weight=ft.FontWeight.W_600)
        self.ring_minggu = ft.Text("0 minggu ini", size=12, color=C.TEXT_DIM, weight=ft.FontWeight.W_600)

        summary_card = ft.Container(
            bgcolor=C.SURFACE_RAISED,
            border=ft.Border.all(1, C.BORDER),
            border_radius=ft.BorderRadius.all(18),
            padding=ft.Padding.all(20),
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.INSIGHTS_ROUNDED, color=C.ACCENT, size=20),
                            ft.Text("RINGKASAN HARI INI", size=12, color=C.TEXT_DIM, weight=ft.FontWeight.W_600),
                        ],
                        spacing=8,
                    ),
                    ft.Container(height=6),
                    ft.Row([self.big_hadir, ft.Container(width=6), self.big_sub], vertical_alignment=ft.CrossAxisAlignment.END),
                    ft.Container(height=8),
                    ft.Row(
                        [
                            ft.Container(
                                content=ft.Row(
                                    [ft.Icon(ft.Icons.SCHEDULE_ROUNDED, size=14, color=C.LATE), self.ring_telat],
                                    spacing=6,
                                ),
                                bgcolor=C.LATE_SOFT, border_radius=ft.BorderRadius.all(999),
                                padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                            ),
                            ft.Container(
                                content=ft.Row(
                                    [ft.Icon(ft.Icons.CALENDAR_VIEW_WEEK_ROUNDED, size=14, color=C.TEXT_DIM), self.ring_minggu],
                                    spacing=6,
                                ),
                                bgcolor=C.SURFACE_ALT, border_radius=ft.BorderRadius.all(999),
                                padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                            ),
                        ],
                        spacing=10,
                    ),
                ],
            ),
        )

        # ---- pintasan 3 metode scan ----
        shortcuts = ft.Row(
            [
                self._method_card("Kartu RFID", ft.Icons.NFC_ROUNDED, C.RFID, C.RFID_SOFT, "rfid"),
                self._method_card("Wajah", ft.Icons.FACE_RETOUCHING_NATURAL_ROUNDED, C.WAJAH, C.WAJAH_SOFT, "wajah"),
                self._method_card("Sidik Jari", ft.Icons.FINGERPRINT_ROUNDED, C.SIDIK, C.SIDIK_SOFT, "sidik"),
            ],
            spacing=10,
        )

        # ---- aktivitas terbaru ----
        self.recent_label = ft.Text("AKTIVITAS TERBARU", size=12, color=C.TEXT_DIM, weight=ft.FontWeight.W_600)
        self.recent_list = ft.Column(spacing=8)
        self.recent_empty = ft.Container(
            content=ft.Text("Belum ada aktivitas hari ini", color=C.TEXT_DIM, size=13),
            alignment=ft.Alignment.CENTER, padding=ft.Padding.symmetric(vertical=24),
        )

        self.container = ft.Container(
            bgcolor=C.BG,
            expand=True,
            padding=ft.Padding.only(top=20, left=16, right=16, bottom=8),
            content=ft.Column(
                [
                    header,
                    ft.Container(height=18),
                    summary_card,
                    ft.Container(height=18),
                    ft.Text("SCAN CEPAT", size=12, color=C.TEXT_DIM, weight=ft.FontWeight.W_600),
                    ft.Container(height=8),
                    shortcuts,
                    ft.Container(height=20),
                    self.recent_label,
                    ft.Container(height=8),
                    ft.Container(
                        content=ft.Column([self.recent_list, self.recent_empty], scroll=ft.ScrollMode.AUTO),
                        expand=True,
                    ),
                ],
                expand=True,
            ),
        )

    def _greeting(self) -> str:
        h = datetime.now().hour
        if h < 11:
            return "Selamat pagi 👋"
        if h < 15:
            return "Selamat siang 👋"
        if h < 18:
            return "Selamat sore 👋"
        return "Selamat malam 👋"

    def _method_card(self, label, icon, color, soft_bg, method_key) -> ft.Container:
        return ft.Container(
            expand=True,
            bgcolor=C.SURFACE,
            border=ft.Border.all(1, C.BORDER),
            border_radius=ft.BorderRadius.all(16),
            padding=ft.Padding.symmetric(vertical=16, horizontal=8),
            on_click=(lambda e, k=method_key: self.on_go_scan(k)) if self.on_go_scan else None,
            content=ft.Column(
                [
                    ft.Container(
                        content=ft.Icon(icon, color=color, size=22),
                        width=44, height=44, border_radius=ft.BorderRadius.all(22),
                        bgcolor=soft_bg, alignment=ft.Alignment.CENTER,
                    ),
                    ft.Container(height=8),
                    ft.Text(label, color=C.TEXT, size=12, weight=ft.FontWeight.W_600, text_align=ft.TextAlign.CENTER),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=0,
            ),
        )

    # ------------------------------------------------------------ data
    async def start(self):
        if self._running:
            return
        self._running = True
        await self.fetch()
        self.page.run_task(self._poll_loop)

    async def _poll_loop(self):
        while self._running:
            await asyncio.sleep(REFRESH_INTERVAL_S)
            await self.fetch()

    async def fetch(self):
        try:
            self.attendance = await api.fetch_attendance()
        except Exception as ex:
            print("Gagal ambil ringkasan beranda:", ex)
            return
        self._render()
        try:
            self.container.update()
        except Exception:
            pass

    def _render(self):
        today_masuk = [i for i in self.attendance if is_today(i["scanned_at"]) and is_masuk_record(i)]
        hadir = len(today_masuk)
        telat = len([i for i in today_masuk if is_late_record(i)])
        minggu = len([i for i in self.attendance if is_this_week(i["scanned_at"]) and is_masuk_record(i)])

        self.big_hadir.value = str(hadir)
        self.ring_telat.value = f"{telat} telat"
        self.ring_minggu.value = f"{minggu} minggu ini"

        recent = sorted(self.attendance, key=lambda i: i["scanned_at"], reverse=True)[:6]
        rows = []
        for item in recent:
            jam, tanggal = format_date_time(item["scanned_at"])
            is_masuk = is_masuk_record(item)
            late = is_late_record(item)
            if is_masuk:
                dot_color = C.LATE if late else C.SUCCESS
                label = "Telat masuk" if late else "Tepat waktu"
            else:
                dot_color = C.KELUAR
                label = "Pulang"
            rows.append(
                ft.Container(
                    bgcolor=C.SURFACE, border=ft.Border.all(1, C.BORDER), border_radius=ft.BorderRadius.all(12),
                    padding=ft.Padding.symmetric(horizontal=14, vertical=12),
                    content=ft.Row(
                        [
                            ft.Container(width=8, height=8, border_radius=ft.BorderRadius.all(4), bgcolor=dot_color),
                            ft.Column(
                                [
                                    ft.Text(item["name"], color=C.TEXT, size=14, weight=ft.FontWeight.W_600),
                                    ft.Text(f"{label} · {jam}", color=C.TEXT_DIM, size=11),
                                ],
                                spacing=2, expand=True,
                            ),
                            ft.Text(tanggal, color=C.TEXT_FAINT, size=11),
                        ],
                        spacing=10,
                    ),
                )
            )
        self.recent_list.controls = rows
        self.recent_empty.visible = len(rows) == 0
