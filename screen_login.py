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

    # Enter di username -> pindah fokus ke password, bukan langsung submit
    # (kebiasaan form login pada umumnya).
    username_field.on_submit = lambda e: password_field.focus()

    async def do_login(e):
        username = (username_field.value or "").strip()
        password = password_field.value or ""
        if not username or not password:
            status_text.value = "Isi username & password dulu."
            status_text.visible = True
            status_text.update()
            return

        # Tampilkan spinner kecil di dalam tombol (konsisten dengan pola
        # loading di CardsView._submit_register), bukan cuma ganti teks.
        login_button.content = ft.Row(
            [
                ft.ProgressRing(color=C.BG, width=14, height=14, stroke_width=2),
                ft.Text("Memproses...", color=C.BG, weight=ft.FontWeight.BOLD),
            ],
            alignment=ft.MainAxisAlignment.CENTER, spacing=8, tight=True,
        )
        login_button.on_click = None
        status_text.visible = False
        login_button.update()
        status_text.update()

        try:
            await api.login(username, password)
        except RuntimeError as ex:
            # Error yang sengaja dilempar api.login() dengan pesan dari
            # server (mis. "Username atau password salah") -- aman
            # ditampilkan langsung ke pengguna.
            status_text.value = str(ex)
        except Exception:
            # Error lain (jaringan putus, URL salah, server tidak
            # reachable) -- pesan asli httpx terlalu teknis untuk
            # pengguna awam, ganti dengan pesan yang mengarahkan solusi.
            status_text.value = "Tidak bisa terhubung ke server. Cek URL Server di bawah."
        else:
            # Login SUDAH berhasil di titik ini. on_success() sengaja di luar
            # blok try di atas supaya error dari show_app() tidak salah
            # dilaporkan sebagai "Tidak bisa terhubung ke server".
            try:
                on_success()
                return  # page sudah diganti main.py, jangan sentuh control ini lagi
            except Exception as ex:
                print("Login berhasil, tapi gagal membuka layar utama:", ex)
                status_text.value = (
                    "Login berhasil, tapi layar utama gagal dibuka. "
                    "Tutup lalu buka ulang aplikasi."
                )
        status_text.visible = True

        login_button.content = login_label
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
        page.pop_dialog()

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
        page.show_dialog(server_dialog)

    # Ikon kecil di sebelah teks supaya terlihat jelas ini bisa diklik,
    # bukan sekadar label info biasa.
    server_text_button = ft.GestureDetector(
        content=ft.Row(
            [
                ft.Icon(ft.Icons.SETTINGS_ETHERNET_ROUNDED, size=12, color=C.TEXT_DIM),
                server_text,
            ],
            spacing=4, alignment=ft.MainAxisAlignment.CENTER, tight=True,
        ),
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