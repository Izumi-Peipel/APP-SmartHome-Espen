"""ScanView — hub 3 metode absensi: RFID, Wajah, Sidik Jari.

RFID  : fungsional penuh (pakai CardsView yang sudah ada, embedded).
Wajah : REAL -- pakai kamera laptop + OpenCV (lihat screen_face.py &
        face_engine.py). Data wajah disimpan lokal di folder face_data/.
Sidik Jari : MASIH MODE SIMULASI -- menunggu sensor fisik (mis. R307/AS608)
terpasang ke ESP32. Ditandai jelas dengan badge 'Mode Simulasi'.
"""

import asyncio
import random
import flet as ft
import theme as C
from screen_cards import CardsView
from screen_face import FaceTab

METHODS = [
    {"key": "rfid", "label": "RFID", "icon": ft.Icons.NFC_ROUNDED, "color": C.RFID, "soft": C.RFID_SOFT},
    {"key": "wajah", "label": "Wajah", "icon": ft.Icons.FACE_RETOUCHING_NATURAL_ROUNDED, "color": C.WAJAH, "soft": C.WAJAH_SOFT},
    {"key": "sidik", "label": "Sidik Jari", "icon": ft.Icons.FINGERPRINT_ROUNDED, "color": C.SIDIK, "soft": C.SIDIK_SOFT},
]

_MOCK_SIDIK = [
    {"name": "Budi Santoso", "jari": "Telunjuk Kanan"},
    {"name": "Rina Wulandari", "jari": "Jempol Kanan"},
]


def _sim_badge(color: str, soft: str) -> ft.Container:
    return ft.Container(
        content=ft.Row(
            [ft.Icon(ft.Icons.SCIENCE_OUTLINED, size=13, color=color),
             ft.Text("Mode Simulasi — hardware belum terpasang", size=11, color=color, weight=ft.FontWeight.W_600)],
            spacing=6, tight=True,
        ),
        bgcolor=soft, border_radius=ft.BorderRadius.all(999),
        padding=ft.Padding.symmetric(horizontal=12, vertical=6),
    )


class ScanView:
    def __init__(self, page: ft.Page):
        self.page = page
        self.active = "rfid"
        self._running = False

        # sub-views
        self.cards_view = CardsView(page, embedded=True)
        self.face_tab = FaceTab(page)
        self._sidik_scanning = False

        self.segmented = ft.Row(spacing=8)
        self._build_segmented()

        self.body_area = ft.Container(expand=True)

        self.container = ft.Container(
            bgcolor=C.BG,
            expand=True,
            padding=ft.Padding.only(top=20, left=16, right=16, bottom=8),
            content=ft.Column(
                [
                    ft.Text("Scan Absensi", size=22, weight=ft.FontWeight.BOLD, color=C.TEXT),
                    ft.Text("Pilih metode yang ingin digunakan", size=12, color=C.TEXT_DIM),
                    ft.Container(height=14),
                    self.segmented,
                    ft.Container(height=14),
                    self.body_area,
                ],
                expand=True,
            ),
        )

        self._render_body()

    # ------------------------------------------------------------ segmented control
    def _build_segmented(self):
        chips = []
        for m in METHODS:
            active = self.active == m["key"]
            chips.append(
                ft.Container(
                    expand=True,
                    bgcolor=m["soft"] if active else C.SURFACE,
                    border=ft.Border.all(1.5 if active else 1, m["color"] if active else C.BORDER),
                    border_radius=ft.BorderRadius.all(12),
                    padding=ft.Padding.symmetric(vertical=10),
                    on_click=lambda e, k=m["key"]: self.set_active(k),
                    content=ft.Column(
                        [
                            ft.Icon(m["icon"], color=m["color"] if active else C.TEXT_DIM, size=18),
                            ft.Text(m["label"], size=11, weight=ft.FontWeight.W_600,
                                    color=m["color"] if active else C.TEXT_DIM),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4,
                    ),
                )
            )
        self.segmented.controls = chips

    def set_active(self, key: str):
        if key == self.active:
            return
        old = self.active
        self.active = key
        self._build_segmented()
        self._render_body()
        try:
            self.segmented.update()
            self.body_area.update()
        except Exception:
            pass

        if old == "wajah":
            self.face_tab.stop()

        if key == "rfid" and self._running:
            self.page.run_task(self.cards_view.start)
        elif key == "wajah":
            self.page.run_task(self.face_tab.start)

    # ------------------------------------------------------------ body per metode
    def _render_body(self):
        if self.active == "rfid":
            self.body_area.content = self.cards_view.container
        elif self.active == "wajah":
            self.body_area.content = self.face_tab.container
        else:
            self.body_area.content = self._build_sidik_body()

    def _build_sidik_body(self) -> ft.Control:
        finger_icon = ft.Icon(ft.Icons.FINGERPRINT_ROUNDED, color=C.SIDIK, size=64)
        status_text = ft.Text("Tempelkan jari ke sensor", color=C.TEXT_DIM, size=12)

        preview_box = ft.Container(
            height=200, bgcolor=C.SIDIK_SOFT, border=ft.Border.all(1.5, C.SIDIK),
            border_radius=ft.BorderRadius.all(18), alignment=ft.Alignment.CENTER,
            content=ft.Column([finger_icon, ft.Container(height=8), status_text],
                               horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=0),
        )

        scan_btn_text = ft.Text("Simulasikan Tempel Jari", color=C.BG, weight=ft.FontWeight.BOLD)
        scan_btn = ft.Container(
            content=scan_btn_text, bgcolor=C.SIDIK, border_radius=ft.BorderRadius.all(10),
            padding=ft.Padding.symmetric(vertical=12), alignment=ft.Alignment.CENTER,
        )

        async def run_sim(e):
            if self._sidik_scanning:
                return
            self._sidik_scanning = True
            scan_btn_text.value = "Membaca sidik jari..."
            status_text.value = "Mencocokkan pola guratan..."
            scan_btn.update()
            status_text.update()
            await asyncio.sleep(1.4)
            person = random.choice(_MOCK_SIDIK)
            status_text.value = f"Simulasi cocok dengan: {person['name']} ({person['jari']})"
            status_text.color = C.SUCCESS
            scan_btn_text.value = "Simulasikan Tempel Jari"
            scan_btn.update()
            status_text.update()
            self._sidik_scanning = False

        scan_btn.on_click = lambda e: self.page.run_task(run_sim, e)

        enrolled_label = ft.Text(f"SIDIK JARI TERDAFTAR (contoh) · {len(_MOCK_SIDIK)}", color=C.TEXT_DIM, size=12,
                                  weight=ft.FontWeight.W_600)
        enrolled_rows = []
        for p in _MOCK_SIDIK:
            enrolled_rows.append(
                ft.Container(
                    bgcolor=C.SURFACE, border=ft.Border.all(1, C.BORDER), border_radius=ft.BorderRadius.all(12),
                    padding=ft.Padding.all(12),
                    content=ft.Row(
                        [
                            ft.Container(
                                content=ft.Icon(ft.Icons.FINGERPRINT_ROUNDED, color=C.SIDIK, size=18),
                                width=36, height=36, border_radius=ft.BorderRadius.all(18),
                                bgcolor=C.SIDIK_SOFT, alignment=ft.Alignment.CENTER,
                            ),
                            ft.Column(
                                [ft.Text(p["name"], color=C.TEXT, size=14, weight=ft.FontWeight.W_600),
                                 ft.Text(p["jari"], color=C.TEXT_DIM, size=11)],
                                spacing=2, expand=True,
                            ),
                        ],
                        spacing=10,
                    ),
                )
            )

        add_finger_btn = ft.Container(
            content=ft.Row(
                [ft.Icon(ft.Icons.ADD_ROUNDED, color=C.SIDIK, size=16),
                 ft.Text("Daftarkan Sidik Jari Baru", color=C.SIDIK, size=13, weight=ft.FontWeight.W_600)],
                spacing=6, alignment=ft.MainAxisAlignment.CENTER,
            ),
            bgcolor=C.SIDIK_SOFT, border=ft.Border.all(1, C.SIDIK), border_radius=ft.BorderRadius.all(10),
            padding=ft.Padding.symmetric(vertical=10),
            on_click=lambda e: self._show_coming_soon("Pendaftaran sidik jari"),
        )

        return ft.Column(
            [
                _sim_badge(C.SIDIK, C.SIDIK_SOFT),
                ft.Container(height=12),
                preview_box,
                ft.Container(height=12),
                scan_btn,
                ft.Container(height=20),
                ft.Row([enrolled_label], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Container(height=8),
                ft.Column(enrolled_rows, spacing=8),
                ft.Container(height=10),
                add_finger_btn,
            ],
            expand=True, scroll=ft.ScrollMode.AUTO,
        )

    def _show_coming_soon(self, feature: str):
        dialog = ft.AlertDialog(
            title=ft.Text("Segera Hadir", color=C.TEXT),
            bgcolor=C.SURFACE,
            content=ft.Text(
                f"{feature} akan aktif setelah hardware terkait terpasang dan "
                "terhubung ke server (mirip alur LWT/MQTT pada reader RFID).",
                color=C.TEXT_DIM,
            ),
            actions=[ft.TextButton(content=ft.Text("Mengerti", color=C.ACCENT), on_click=lambda e: self.page.pop_dialog())],
        )
        self.page.show_dialog(dialog)

    def open_method(self, key: str):
        """Dipanggil dari luar (mis. pintasan di Beranda) untuk langsung
        membuka tab metode tertentu."""
        self.set_active(key)

    # ------------------------------------------------------------ lifecycle
    async def start(self):
        if self._running:
            return
        self._running = True
        await self.cards_view.start()

    def stop(self):
        self._running = False
        self.cards_view._running = False
        self.face_tab.stop()
