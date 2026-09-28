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

    # ---------------------------------------------------------- ganti URL server
    # Diletakkan di layar Login (bukan cuma di tab Pengaturan) supaya user
    # tidak terjebak kalau URL default/tersimpan salah -- tanpa ini, user
    # tidak akan pernah berhasil login untuk membuka Pengaturan.
    server_url_field = ft.TextField(
        label="URL Server",
        hint_text="https://xxxxx.up.railway.app",
        color=C.TEXT, bgcolor=C.SURFACE_ALT, border_color=C.BORDER,
        content_padding=ft.Padding.symmetric(horizontal=12, vertical=10),
    )
    server_dialog_status = ft.Text("", color=C.DANGER, size=12, visible=False)
    server_text = ft.Text(
        f"Server: {api.get_base_url()}",
        color=C.TEXT_DIM, size=11, text_align=ft.TextAlign.CENTER,
    )

    server_dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("Ganti URL Server", color=C.TEXT),
        content=ft.Column(
            [server_url_field, server_dialog_status],
            tight=True, spacing=8,
        ),
        bgcolor=C.SURFACE,
    )

    def close_server_dialog(e=None):
        server_dialog.open = False
        page.update()

    async def save_server_url(e):
        new_url = (server_url_field.value or "").strip()
        if not new_url:
            server_dialog_status.value = "URL tidak boleh kosong."
            server_dialog_status.visible = True
            server_dialog_status.update()
            return
        if not (new_url.startswith("http://") or new_url.startswith("https://")):
            server_dialog_status.value = "URL harus diawali http:// atau https://"
            server_dialog_status.visible = True
            server_dialog_status.update()
            return
        await api.save_base_url(page, new_url)
        server_text.value = f"Server: {api.get_base_url()}"
        close_server_dialog()
        server_text.update()

    server_dialog.actions = [
        ft.TextButton("Batal", on_click=close_server_dialog),
        ft.TextButton("Simpan", on_click=lambda e: page.run_task(save_server_url, e)),
    ]

    def open_server_dialog(e):
        server_url_field.value = api.get_base_url()
        server_dialog_status.visible = False
        page.open(server_dialog) if hasattr(page, "open") else _open_dialog_fallback()

    def _open_dialog_fallback():
        # Fallback untuk versi Flet yang belum punya page.open() -- daftarkan
        # dialog ke overlay lalu buka manual.
        if server_dialog not in page.overlay:
            page.overlay.append(server_dialog)
        server_dialog.open = True
        page.update()

    server_text_button = ft.GestureDetector(
        content=server_text,
        on_tap=open_server_dialog,
    )

    return ft.Container(
        bgcolor=C.BG,
        expand=True,
        alignment=ft.Alignment.CENTER,
        padding=ft.Padding.all(24),
        content=ft.Column(
            [
                ft.Container(
                    content=ft.Icon(ft.Icons.FINGERPRINT_ROUNDED, size=32, color=C.ACCENT),
                    width=64, height=64, border_radius=ft.BorderRadius.all(20),
                    bgcolor=C.ACCENT_SOFT, alignment=ft.Alignment.CENTER,
                ),
                ft.Container(height=6),
                ft.Text("Absensi Digital", size=22, weight=ft.FontWeight.BOLD, color=C.TEXT),
                ft.Text("Masuk untuk melanjutkan", color=C.TEXT_DIM, size=13),
                ft.Container(height=20),
                username_field,
                password_field,
                status_text,
                ft.Container(height=8),
                login_button,
                ft.Container(height=4),
                server_text_button,
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
            width=320,
        ),
    )