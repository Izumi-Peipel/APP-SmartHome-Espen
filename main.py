"""Aplikasi mobile Absensi RFID + CCTV (mock) — port dari cctv-app5 (Expo/RN)
ke Flet (Python). Jalankan dengan: flet run main.py

BASE_URL backend ada di api.py — samakan dengan domain ngrok kamu.
"""

import flet as ft
import theme as C
import api
from screens_static import build_live_view, build_history_view
from screen_attendance import AttendanceView
from screen_cards import CardsView
from screen_settings import build_settings_view
from screen_login import build_login_view


async def main(page: ft.Page):
    page.title = "CCTV App Espen"
    page.bgcolor = C.BG
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 0
    page.spacing = 0

    # ---- setup api.py: base URL & sesi login tersimpan ----
    api.set_page(page)
    await api.load_base_url(page)
    await api.load_session()

    # dipegang di sini supaya show_login() bisa menghentikan polling
    # tab Absensi & Kartu yang lagi jalan, sebelum ganti layar
    running_views = {"attendance": None, "cards": None}

    def _stop_background_polling():
        if running_views["attendance"] is not None:
            running_views["attendance"]._running = False
        if running_views["cards"] is not None:
            running_views["cards"]._running = False
        running_views["attendance"] = None
        running_views["cards"] = None

    def show_login():
        _stop_background_polling()
        page.navigation_bar = None
        page.controls.clear()
        page.add(build_login_view(page, on_success=show_app))
        page.update()

    def show_app():
        page.controls.clear()

        live_view = build_live_view()
        history_view = build_history_view()
        attendance_view = AttendanceView(page)
        cards_view = CardsView(page)
        settings_view = build_settings_view(page, on_logout=show_login)

        running_views["attendance"] = attendance_view
        running_views["cards"] = cards_view

        views = {
            0: live_view,
            1: history_view,
            2: attendance_view.container,
            3: cards_view.container,
            4: settings_view,
        }

        content_area = ft.Container(content=views[0], expand=True)

        def on_nav_change(e):
            content_area.content = views[e.control.selected_index]
            content_area.update()

        page.navigation_bar = ft.NavigationBar(
            selected_index=0,
            bgcolor=C.SURFACE,
            indicator_color=C.ACCENT,
            on_change=on_nav_change,
            destinations=[
                ft.NavigationBarDestination(icon=ft.Icons.VIDEOCAM_OUTLINED, selected_icon=ft.Icons.VIDEOCAM, label="Live"),
                ft.NavigationBarDestination(icon=ft.Icons.SCHEDULE_OUTLINED, selected_icon=ft.Icons.SCHEDULE, label="Riwayat"),
                ft.NavigationBarDestination(icon=ft.Icons.BADGE_OUTLINED, selected_icon=ft.Icons.BADGE, label="Absensi"),
                ft.NavigationBarDestination(icon=ft.Icons.CREDIT_CARD_OUTLINED, selected_icon=ft.Icons.CREDIT_CARD, label="Kartu"),
                ft.NavigationBarDestination(icon=ft.Icons.SETTINGS_OUTLINED, selected_icon=ft.Icons.SETTINGS, label="Pengaturan"),
            ],
        )

        page.add(content_area)
        page.update()

        # ---- mulai fetch & polling data real (absensi tiap 15s, kartu tiap 3s) ----
        page.run_task(attendance_view.start)
        page.run_task(cards_view.start)

    async def on_unauthorized():
        # Dipanggil otomatis oleh api.py kalau server balas 401 di tengah
        # pemakaian (sesi kedaluwarsa / dihapus dari server). Bersihkan
        # token lokal lalu lempar balik ke layar Login.
        await api.force_logout()
        show_login()

    api.set_unauthorized_handler(on_unauthorized)

    # ---- tentukan layar awal: validasi token tersimpan (kalau ada) ke server ----
    me = await api.fetch_me() if api.is_logged_in() else None
    if me:
        show_app()
    else:
        show_login()


ft.run(main)