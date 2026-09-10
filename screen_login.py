"""LoginScreen — layar login sebelum masuk ke app utama.
Dipanggil dari main.py; on_success dipanggil setelah login berhasil supaya
main.py bisa mengganti isi page ke navigasi utama."""

import flet as ft
import theme as C
import api


def build_login_view(page: ft.Page, on_success) -> ft.Control:
    username_field = ft.TextField(
        label="Username",
        color=C.TEXT, bgcolor=C.SURFACE_ALT, border_color=C.BORDER,
        content_padding=ft.Padding.symmetric(horizontal=12, vertical=10),
        autofocus=True,
    )
    password_field = ft.TextField(
        label="Password",
        password=True, can_reveal_password=True,
        color=C.TEXT, bgcolor=C.SURFACE_ALT, border_color=C.BORDER,
        content_padding=ft.Padding.symmetric(horizontal=12, vertical=10),
    )
    status_text = ft.Text("", color=C.DANGER, size=12, visible=False, text_align=ft.TextAlign.CENTER)
    login_label = ft.Text("Masuk", color=C.BG, weight=ft.FontWeight.BOLD)

    login_button = ft.Container(
        content=login_label, bgcolor=C.ACCENT, border_radius=ft.BorderRadius.all(10),
        padding=ft.Padding.symmetric(vertical=14), alignment=ft.Alignment.CENTER,
    )

    async def do_login(e):
        username = (username_field.value or "").strip()
        password = password_field.value or ""
        if not username or not password:
            status_text.value = "Isi username & password dulu."
            status_text.visible = True
            status_text.update()
            return

        login_label.value = "Memproses..."
        login_button.on_click = None
        status_text.visible = False
        login_button.update()
        status_text.update()

        try:
            await api.login(username, password)
            on_success()
            return  # page sudah diganti main.py, jangan sentuh control ini lagi
        except Exception as ex:
            status_text.value = str(ex)
            status_text.visible = True

        login_label.value = "Masuk"
        login_button.on_click = lambda e: page.run_task(do_login, e)
        try:
            login_button.update()
            status_text.update()
        except Exception:
            pass

    login_button.on_click = lambda e: page.run_task(do_login, e)
    password_field.on_submit = lambda e: page.run_task(do_login, e)

    return ft.Container(
        bgcolor=C.BG,
        expand=True,
        alignment=ft.Alignment.CENTER,
        padding=ft.Padding.all(24),
        content=ft.Column(
            [
                ft.Icon(ft.Icons.VIDEOCAM, size=48, color=C.ACCENT),
                ft.Text("CCTV App Espen", size=22, weight=ft.FontWeight.BOLD, color=C.TEXT),
                ft.Text("Masuk untuk melanjutkan", color=C.TEXT_DIM, size=13),
                ft.Container(height=20),
                username_field,
                password_field,
                status_text,
                ft.Container(height=8),
                login_button,
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
            width=320,
        ),
    )
