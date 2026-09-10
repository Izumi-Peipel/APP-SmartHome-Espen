"""AttendanceScreen — port dari App.js. Fetch berkala ke backend, statistik,
pencarian, filter tanggal, absen manual, dan detail riwayat per orang."""

import asyncio
import flet as ft
import theme as C
import api
from utils import (
    format_date_time, is_today, is_this_week, is_masuk_record, is_late_record, to_date,
)

POLL_INTERVAL_S = 15


def attendance_badge(item: dict) -> ft.Control:
    is_masuk = is_masuk_record(item)
    late = is_late_record(item)

    if is_masuk:
        chips = [
            ft.Container(
                content=ft.Text("Masuk", color="#6FB3FF", size=11, weight=ft.FontWeight.W_600),
                bgcolor="#1C2A3A", border=ft.Border.all(1, "#2C5A8A"),
                padding=ft.Padding.symmetric(horizontal=8, vertical=3), border_radius=ft.BorderRadius.all(6),
            )
        ]
        if late:
            chips.append(
                ft.Container(
                    content=ft.Text("Telat", color=C.LATE, size=11, weight=ft.FontWeight.W_600),
                    bgcolor="#3A2A1C", border=ft.Border.all(1, "#8A5A2C"),
                    padding=ft.Padding.symmetric(horizontal=8, vertical=3), border_radius=ft.BorderRadius.all(6),
                )
            )
        return ft.Column(chips, horizontal_alignment=ft.CrossAxisAlignment.END, spacing=4)

    chips = [
        ft.Container(
            content=ft.Text("Keluar", color=C.KELUAR, size=11, weight=ft.FontWeight.W_600),
            bgcolor="#2A1C3A", border=ft.Border.all(1, "#5A2C8A"),
            padding=ft.Padding.symmetric(horizontal=8, vertical=3), border_radius=ft.BorderRadius.all(6),
        )
    ]
    durasi = item.get("durasi_jam")
    if isinstance(durasi, (int, float)):
        chips.append(ft.Text(f"{durasi:.1f} jam", color=C.TEXT_DIM, size=11))
    return ft.Column(chips, horizontal_alignment=ft.CrossAxisAlignment.END, spacing=4)


class AttendanceView:
    def __init__(self, page: ft.Page):
        self.page = page
        self.attendance: list[dict] = []
        self.loading = True
        self.search = ""
        self.date_filter = "today"  # today | week | all | custom
        self.custom_date: str | None = None
        self.last_count: int | None = None
        self._running = False

        # ---- controls ----
        self.title_row = ft.Row(
            [
                ft.Text("Absensi", size=22, weight=ft.FontWeight.BOLD, color=C.TEXT),
                ft.Row(
                    [
                        ft.IconButton(icon=ft.Icons.REFRESH, icon_color=C.TEXT_DIM, on_click=self._on_refresh_click),
                        ft.IconButton(icon=ft.Icons.ADD_CIRCLE_OUTLINE, icon_color=C.ACCENT, on_click=self._open_manual),
                    ],
                    spacing=0,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        self.notif_banner = ft.Container(visible=False)

        self.stat_hadir = ft.Text("0", size=20, weight=ft.FontWeight.BOLD, color=C.TEXT)
        self.stat_telat = ft.Text("0", size=20, weight=ft.FontWeight.BOLD, color=C.LATE)
        self.stat_minggu = ft.Text("0", size=20, weight=ft.FontWeight.BOLD, color=C.TEXT)
        stats_row = ft.Row(
            [
                self._stat_box(self.stat_hadir, "Hadir Hari Ini"),
                self._stat_box(self.stat_telat, "Telat Hari Ini"),
                self._stat_box(self.stat_minggu, "Minggu Ini"),
            ],
            spacing=10,
        )

        self.search_field = ft.TextField(
            hint_text="Cari nama...", color=C.TEXT, bgcolor=C.SURFACE, border_color=C.BORDER,
            content_padding=ft.Padding.symmetric(horizontal=12, vertical=10),
            on_change=self._on_search_change, expand=True, border_radius=10,
        )
        search_box = ft.Row(
            [
                ft.Icon(ft.Icons.SEARCH_OUTLINED, color=C.TEXT_DIM, size=18),
                self.search_field,
                ft.IconButton(icon=ft.Icons.PEOPLE_OUTLINE, icon_color=C.ACCENT, on_click=self._open_name_picker),
            ],
            spacing=8,
        )

        self.filter_chips_row = ft.Row(spacing=8, scroll=ft.ScrollMode.AUTO)
        self._build_filter_chips()

        self.list_view = ft.ListView(spacing=10, expand=True)
        self.empty_state = ft.Container(
            content=ft.Column(
                [ft.Icon(ft.Icons.INBOX_OUTLINED, size=32, color=C.TEXT_DIM),
                 ft.Text("Belum ada data absensi", color=C.TEXT_DIM)],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            alignment=ft.Alignment.CENTER, expand=True, visible=False,
        )
        self.loading_state = ft.Container(
            content=ft.ProgressRing(color=C.ACCENT), alignment=ft.Alignment.CENTER, expand=True,
        )
        self.list_area = ft.Stack([self.list_view, self.empty_state, self.loading_state], expand=True)

        self.container = ft.Container(
            bgcolor=C.BG,
            expand=True,
            padding=ft.Padding.only(top=16, left=16, right=16, bottom=8),
            content=ft.Column(
                [
                    self.title_row,
                    self.notif_banner,
                    ft.Container(height=8),
                    stats_row,
                    ft.Container(height=10),
                    search_box,
                    ft.Container(height=10),
                    self.filter_chips_row,
                    ft.Container(height=8),
                    self.list_area,
                ],
                expand=True,
            ),
        )

    # ---------------------------------------------------------------- UI bits
    def _stat_box(self, value_ctrl: ft.Text, label: str) -> ft.Container:
        return ft.Container(
            content=ft.Column(
                [value_ctrl, ft.Text(label, size=11, color=C.TEXT_DIM, text_align=ft.TextAlign.CENTER)],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4,
            ),
            bgcolor=C.SURFACE, border=ft.Border.all(1, C.BORDER), border_radius=ft.BorderRadius.all(12),
            padding=ft.Padding.symmetric(vertical=12), expand=True, alignment=ft.Alignment.CENTER,
        )

    def _build_filter_chips(self):
        options = [("today", "Hari Ini"), ("week", "Minggu Ini"), ("all", "Semua")]
        chips = []
        for key, label in options:
            active = self.date_filter == key
            chips.append(self._filter_chip(label, active, lambda e, k=key: self._set_date_filter(k)))
        active_custom = self.date_filter == "custom"
        custom_label = "Tanggal"
        if active_custom and self.custom_date:
            custom_label = format_date_time(f"{self.custom_date}T00:00:00")[1]
        chips.append(
            self._filter_chip(custom_label, active_custom, self._open_date_picker, icon=ft.Icons.CALENDAR_MONTH_OUTLINED)
        )
        self.filter_chips_row.controls = chips

    def _filter_chip(self, label, active, on_click, icon=None) -> ft.Container:
        row_children = []
        if icon:
            row_children.append(ft.Icon(icon, size=13, color=C.BG if active else C.TEXT_DIM))
        row_children.append(
            ft.Text(label, size=12, weight=ft.FontWeight.W_600, color=C.BG if active else C.TEXT_DIM)
        )
        return ft.Container(
            content=ft.Row(row_children, spacing=4, tight=True),
            bgcolor=C.ACCENT if active else C.SURFACE,
            border=ft.Border.all(1, C.ACCENT if active else C.BORDER),
            border_radius=ft.BorderRadius.all(999),
            padding=ft.Padding.symmetric(horizontal=14, vertical=6),
            on_click=on_click,
        )

    # ---------------------------------------------------------------- state
    def _set_date_filter(self, key: str):
        self.date_filter = key
        self._build_filter_chips()
        self._render()
        self.filter_chips_row.update()

    def _on_search_change(self, e):
        self.search = e.control.value or ""
        self._render()
        self.list_area.update()

    # ---------------------------------------------------------------- data
    def _on_refresh_click(self, e):
        # Tombol refresh manual: langsung fetch ulang tanpa nunggu poll 15 detik.
        # Tampilkan loading ring sebentar biar ada feedback ke user.
        self.loading = True
        self._render()
        self.list_area.update()
        self.page.run_task(self.fetch_attendance)

    async def fetch_attendance(self, is_poll: bool = False):
        try:
            data = await api.fetch_attendance()
            sorted_data = sorted(data, key=lambda x: to_date(x["scanned_at"]), reverse=True)

            if is_poll and self.last_count is not None and len(sorted_data) > self.last_count:
                newest = sorted_data[0]
                await self._maybe_notify_new_record(newest)

            self.attendance = sorted_data
            self.last_count = len(sorted_data)
            self.loading = False
            self._render()
            self.container.update()
        except Exception as ex:
            self.loading = False
            self._render()
            try:
                self.container.update()
            except Exception:
                pass
            print("Gagal ambil data absensi:", ex)

    async def _maybe_notify_new_record(self, item: dict):
        # Notif untuk absen "masuk" yang telat dikontrol oleh toggle
        # "Absen terlambat" di Pengaturan Notifikasi. Absen biasa (tepat
        # waktu / pulang) tetap ditampilkan sebagai info dasar, bukan
        # bagian dari pengaturan notifikasi.
        jam, _tanggal = format_date_time(item["scanned_at"])

        if is_masuk_record(item) and is_late_record(item):
            try:
                settings = await api.fetch_notification_settings()
            except Exception as ex:
                print("Gagal cek pengaturan notifikasi, tampilkan default:", ex)
                settings = {"late_attendance": True}

            if settings.get("late_attendance", True):
                self._show_notif(f"⏰ {item['name']} TELAT masuk ({jam})", urgent=True)
            else:
                self._show_notif(f"{item['name']} baru saja absen ({jam})")
        else:
            self._show_notif(f"{item['name']} baru saja absen ({jam})")

    def _show_notif(self, text: str, urgent: bool = False):
        self.notif_banner.content = ft.Row(
            [ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED if urgent else ft.Icons.NOTIFICATIONS, color=C.BG, size=16),
             ft.Text(text, color=C.BG, size=12, weight=ft.FontWeight.W_600, expand=True)],
            spacing=8,
        )
        self.notif_banner.bgcolor = C.LATE if urgent else C.ACCENT
        self.notif_banner.padding = ft.Padding.symmetric(horizontal=12, vertical=8)
        self.notif_banner.border_radius = ft.BorderRadius.all(10)
        self.notif_banner.visible = True
        self.notif_banner.update()

        async def _hide():
            await asyncio.sleep(4)
            self.notif_banner.visible = False
            self.notif_banner.update()

        self.page.run_task(_hide)

    async def start(self):
        if self._running:
            return
        self._running = True
        await self.fetch_attendance()
        self.page.run_task(self._poll_loop)

    async def _poll_loop(self):
        while self._running:
            await asyncio.sleep(POLL_INTERVAL_S)
            await self.fetch_attendance(is_poll=True)

    # ---------------------------------------------------------------- render
    def _filtered(self) -> list[dict]:
        def date_ok(item):
            if self.date_filter == "today":
                return is_today(item["scanned_at"])
            if self.date_filter == "week":
                return is_this_week(item["scanned_at"])
            if self.date_filter == "custom" and self.custom_date:
                return item["scanned_at"].startswith(self.custom_date)
            return True

        date_filtered = [i for i in self.attendance if date_ok(i)]
        q = self.search.lower()
        return [i for i in date_filtered if q in i["name"].lower()]

    def _render(self):
        # stats
        today_masuk = [i for i in self.attendance if is_today(i["scanned_at"]) and is_masuk_record(i)]
        hadir = len([i for i in today_masuk if not is_late_record(i)])
        telat = len([i for i in today_masuk if is_late_record(i)])
        minggu = len([i for i in self.attendance if is_this_week(i["scanned_at"]) and is_masuk_record(i)])
        self.stat_hadir.value = str(hadir)
        self.stat_telat.value = str(telat)
        self.stat_minggu.value = str(minggu)

        filtered = self._filtered()

        self.loading_state.visible = self.loading
        self.empty_state.visible = (not self.loading) and len(filtered) == 0
        self.list_view.visible = (not self.loading) and len(filtered) > 0

        rows = []
        for item in filtered:
            jam, tanggal = format_date_time(item["scanned_at"])
            rows.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Column(
                                [
                                    ft.Text(item["name"], color=C.TEXT, size=15, weight=ft.FontWeight.W_600),
                                    ft.Text(f"{tanggal} · {jam}", color=C.TEXT_DIM, size=12),
                                ],
                                spacing=2, expand=True,
                            ),
                            attendance_badge(item),
                        ],
                    ),
                    bgcolor=C.SURFACE, border=ft.Border.all(1, C.BORDER), border_radius=ft.BorderRadius.all(12),
                    padding=ft.Padding.all(12),
                    on_click=lambda e, name=item["name"]: self._open_person_detail(name),
                )
            )
        self.list_view.controls = rows

    # ---------------------------------------------------------------- dialogs
    def _open_manual(self, e):
        name_field = ft.TextField(hint_text="Nama", color=C.TEXT, bgcolor=C.SURFACE_ALT,
                                   border_color=C.BORDER, autofocus=True)
        status_text = ft.Text("", color=C.DANGER, size=12)

        async def submit(e):
            name = (name_field.value or "").strip()
            if not name:
                status_text.value = "Isi nama dulu sebelum absen manual."
                status_text.update()
                return
            try:
                await api.post_manual_attendance(name)
                self.page.pop_dialog()
                await self.fetch_attendance()
            except Exception as ex:
                status_text.value = f"Gagal mengirim absen manual: {ex}"
                status_text.update()

        dialog = ft.AlertDialog(
            title=ft.Text("Absen Manual", color=C.TEXT),
            bgcolor=C.SURFACE,
            content=ft.Column([name_field, status_text], tight=True, spacing=8),
            actions=[
                ft.TextButton(content=ft.Text("Batal", color=C.TEXT_DIM), on_click=lambda e: self.page.pop_dialog()),
                ft.ElevatedButton(content=ft.Text("Kirim"), bgcolor=C.ACCENT, color=C.BG,
                                   on_click=lambda e: self.page.run_task(submit, e)),
            ],
        )
        self.page.show_dialog(dialog)

    def _open_person_detail(self, name: str):
        history = [i for i in self.attendance if i["name"] == name]
        rows = []
        for item in history:
            jam, tanggal = format_date_time(item["scanned_at"])
            rows.append(
                ft.Row(
                    [ft.Text(f"{tanggal} · {jam}", color=C.TEXT_DIM, size=12), attendance_badge(item)],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                )
            )
        content = ft.Column(rows, spacing=10, scroll=ft.ScrollMode.AUTO) if rows else ft.Text(
            "Tidak ada riwayat", color=C.TEXT_DIM, text_align=ft.TextAlign.CENTER
        )
        dialog = ft.AlertDialog(
            title=ft.Text(name, color=C.TEXT), bgcolor=C.SURFACE,
            content=ft.Container(content=content, width=340, height=300),
            actions=[ft.TextButton(content=ft.Text("Tutup", color=C.TEXT_DIM), on_click=lambda e: self.page.pop_dialog())],
        )
        self.page.show_dialog(dialog)

    def _open_date_picker(self, e):
        unique_dates = sorted({i["scanned_at"][:10] for i in self.attendance}, reverse=True)
        items = []
        for d in unique_dates:
            def pick(e, d=d):
                self.custom_date = d
                self.date_filter = "custom"
                self._build_filter_chips()
                self._render()
                self.page.pop_dialog()
                self.filter_chips_row.update()
                self.list_area.update()

            items.append(
                ft.Container(
                    content=ft.Text(format_date_time(f"{d}T00:00:00")[1], color=C.TEXT),
                    padding=ft.Padding.symmetric(vertical=10), on_click=pick,
                )
            )
        content = ft.Column(items, scroll=ft.ScrollMode.AUTO) if items else ft.Text(
            "Belum ada data absensi", color=C.TEXT_DIM
        )
        dialog = ft.AlertDialog(
            title=ft.Text("Pilih Tanggal", color=C.TEXT), bgcolor=C.SURFACE,
            content=ft.Container(content=content, width=320, height=320),
            actions=[ft.TextButton(content=ft.Text("Tutup", color=C.TEXT_DIM), on_click=lambda e: self.page.pop_dialog())],
        )
        self.page.show_dialog(dialog)

    def _open_name_picker(self, e):
        unique_names = sorted({i["name"] for i in self.attendance})
        items = []
        for n in unique_names:
            def pick(e, n=n):
                self.search = n
                self.search_field.value = n
                self._render()
                self.page.pop_dialog()
                self.search_field.update()
                self.list_area.update()

            items.append(
                ft.Container(content=ft.Text(n, color=C.TEXT), padding=ft.Padding.symmetric(vertical=10), on_click=pick)
            )
        content = ft.Column(items, scroll=ft.ScrollMode.AUTO) if items else ft.Text(
            "Belum ada data absensi", color=C.TEXT_DIM
        )
        dialog = ft.AlertDialog(
            title=ft.Text("Pilih Nama", color=C.TEXT), bgcolor=C.SURFACE,
            content=ft.Container(content=content, width=320, height=320),
            actions=[ft.TextButton(content=ft.Text("Tutup", color=C.TEXT_DIM), on_click=lambda e: self.page.pop_dialog())],
        )
        self.page.show_dialog(dialog)