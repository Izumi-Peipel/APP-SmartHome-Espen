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


def _build_splash_view() -> ft.Container:
    """Layar sementara yang tampil selagi app mengecek sesi login ke
    server (bisa makan waktu beberapa detik, apalagi kalau backend gratis
    seperti Railway free tier sedang 'tidur' dan perlu wake-up). Tanpa
    ini, layar kelihatan blank/putih kosong sebelum Login/Beranda muncul.
    """
    return ft.Container(
        bgcolor=C.BG,
        expand=True,
        alignment=ft.Alignment.CENTER,
        content=ft.Column(
            [
                ft.Container(
                    content=ft.Icon(ft.Icons.BADGE_ROUNDED, color=C.ACCENT, size=40),
                    width=84, height=84, border_radius=ft.BorderRadius.all(24),
                    bgcolor=C.ACCENT_SOFT, alignment=ft.Alignment.CENTER,
                ),
                ft.Container(height=18),
                ft.Text("Absensi Digital", size=20, weight=ft.FontWeight.BOLD, color=C.TEXT),
                ft.Text("Menyiapkan sesi...", size=12, color=C.TEXT_DIM),
                ft.Container(height=22),
                ft.ProgressRing(color=C.ACCENT, width=26, height=26, stroke_width=3),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=2,
        ),
    )


async def main(page: ft.Page):
    page.title = "Absensi Digital"
    page.window.icon = "icon.png"
    page.bgcolor = C.BG
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 0
    page.spacing = 0

    # ---- splash screen sementara proses startup (cek sesi ke server) ----
    # show_login()/show_app() di bawah sama-sama memanggil page.controls.clear()
    # sebelum menampilkan layar sebenarnya, jadi splash ini otomatis hilang
    # begitu salah satu dipanggil -- tidak perlu dibersihkan manual.
    page.add(_build_splash_view())
    page.update()

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
            switcher.content = views[2]
            switcher.update()
            nav_bar_ref["bar"].update()
            scan_view.request_start()
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

        # AnimatedSwitcher memberi transisi fade halus tiap ganti tab,
        # alih-alih tampilan yang "loncat" langsung. Durasi dibuat singkat
        # (150ms) supaya terasa responsif, bukan lambat.
        switcher = ft.AnimatedSwitcher(
            content=views[0],
            transition=ft.AnimatedSwitcherTransition.FADE,
            duration=150,
            reverse_duration=100,
            switch_in_curve=ft.AnimationCurve.EASE_OUT,
            switch_out_curve=ft.AnimationCurve.EASE_IN,
            expand=True,
        )
        content_area = ft.Container(content=switcher, expand=True)

        def on_nav_change(e):
            idx = e.control.selected_index
            switcher.content = views[idx]
            switcher.update()
            if idx == 2:
                scan_view.request_start()
            else:
                # Keluar dari tab Scan -> hentikan polling RFID (hemat baterai
                # & kuota). start() dipanggil lagi otomatis saat kembali ke Scan.
                scan_view.stop()

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