"""Aplikasi mobile Absensi Digital (RFID + Wajah* + Sidik Jari*) — Flet.
*Wajah & Sidik Jari masih mode simulasi/mockup, lihat screen_scan.py.

Jalankan dengan: flet run main.py
BASE_URL backend ada di api.py.
"""

import flet as ft
import theme as C
import api
from screen_home import HomeView
from screen_attendance import AttendanceView
from screen_scan import ScanView
from screen_settings import build_settings_view
from screen_login import build_login_view


async def main(page: ft.Page):
    page.title = "Absensi Digital"
    page.window.icon = "icon.png"
    page.bgcolor = C.BG
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 0
    page.spacing = 0

    # ---- setup api.py: base URL & sesi login tersimpan ----
    api.set_page(page)
    await api.load_base_url(page)
    await api.load_session()

    # dipegang di sini supaya show_login() bisa menghentikan polling
    # tab Beranda, Absensi & Scan yang lagi jalan, sebelum ganti layar
    running_views = {"home": None, "attendance": None, "scan": None}

    def _stop_background_polling():
        if running_views["home"] is not None:
            running_views["home"]._running = False
        if running_views["attendance"] is not None:
            running_views["attendance"]._running = False
        if running_views["scan"] is not None:
            running_views["scan"].stop()
        running_views["home"] = None
        running_views["attendance"] = None
        running_views["scan"] = None

    def show_login():
        _stop_background_polling()
        page.navigation_bar = None
        page.controls.clear()
        page.add(build_login_view(page, on_success=show_app))
        page.update()

    def show_app():
        page.controls.clear()

        nav_bar_ref = {"bar": None}

        def go_to_scan(method_key=None):
            nav_bar_ref["bar"].selected_index = 2
            content_area.content = views[2]
            content_area.update()
            nav_bar_ref["bar"].update()
            page.run_task(scan_view.start)
            if method_key:
                scan_view.open_method(method_key)

        home_view = HomeView(page, on_go_scan=go_to_scan)
        attendance_view = AttendanceView(page)
        scan_view = ScanView(page)
        settings_view = build_settings_view(page, on_logout=show_login)

        running_views["home"] = home_view
        running_views["attendance"] = attendance_view
        running_views["scan"] = scan_view

        views = {
            0: home_view.container,
            1: attendance_view.container,
            2: scan_view.container,
            3: settings_view,
        }

        content_area = ft.Container(content=views[0], expand=True)

        def on_nav_change(e):
            idx = e.control.selected_index
            content_area.content = views[idx]
            content_area.update()
            if idx == 2:
                page.run_task(scan_view.start)

        nav_bar = ft.NavigationBar(
            selected_index=0,
            bgcolor=C.SURFACE,
            indicator_color=C.ACCENT_SOFT,
            on_change=on_nav_change,
            destinations=[
                ft.NavigationBarDestination(icon=ft.Icons.HOME_OUTLINED, selected_icon=ft.Icons.HOME_ROUNDED, label="Beranda"),
                ft.NavigationBarDestination(icon=ft.Icons.BADGE_OUTLINED, selected_icon=ft.Icons.BADGE_ROUNDED, label="Absensi"),
                ft.NavigationBarDestination(icon=ft.Icons.QR_CODE_SCANNER_OUTLINED, selected_icon=ft.Icons.QR_CODE_SCANNER_ROUNDED, label="Scan"),
                ft.NavigationBarDestination(icon=ft.Icons.SETTINGS_OUTLINED, selected_icon=ft.Icons.SETTINGS_ROUNDED, label="Pengaturan"),
            ],
        )
        nav_bar_ref["bar"] = nav_bar
        page.navigation_bar = nav_bar

        page.add(content_area)
        page.update()

        # ---- mulai fetch & polling data real (beranda tiap 20s, absensi tiap 15s) ----
        page.run_task(home_view.start)
        page.run_task(attendance_view.start)

    async def on_unauthorized():
        # Dipanggil otomatis oleh api.py kalau server balas 401 di tengah
        # pemakaian (sesi kedaluwarsa / dihapus dari server). Bersihkan
        # token lokal lalu lempar balik ke layar Login.
        await api.force_logout()
        show_login()

    api.set_unauthorized_handler(on_unauthorized)

    # ---- tentukan layar awal: validasi token tersimpan (kalau ada) ke server ----
    # Dibungkus try/except: kalau backend tidak bisa dihubungi (mis. server
    # belum jalan, URL ngrok kadaluarsa, tidak ada internet), app TETAP
    # membuka layar Login (bukan crash total) supaya user bisa cek/ganti
    # URL backend lewat tab Pengaturan setelah masuk lagi.
    me = None
    try:
        if api.is_logged_in():
            me = await api.fetch_me()
    except Exception as ex:
        print("Gagal menghubungi backend saat startup (lanjut ke layar Login):", ex)

    if me:
        show_app()
    else:
        show_login()


ft.run(main, assets_dir="assets")