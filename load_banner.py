"""Banner kecil "Gagal memuat, coba lagi" yang dipakai layar Beranda,
Absensi, dan Kartu. Tujuannya membedakan "data gagal dimuat" dari
"data memang kosong". Banner tersembunyi secara default; layar yang
memakainya mengatur `banner.visible` sesuai hasil fetch terakhir."""

import flet as ft
import theme as C


def build_load_error_banner(on_retry) -> ft.Container:
    """on_retry: callable sinkron dengan satu argumen (event), biasanya
    `lambda e: page.run_task(self.fetch)`. Seluruh banner bisa diketuk."""
    return ft.Container(
        visible=False,
        ink=True,
        on_click=on_retry,
        bgcolor=C.LATE_SOFT,
        border=ft.Border.all(1, C.LATE),
        border_radius=ft.BorderRadius.all(10),
        padding=ft.Padding.symmetric(horizontal=12, vertical=8),
        content=ft.Row(
            [
                ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=C.LATE, size=16),
                ft.Text("Gagal memuat, coba lagi", color=C.LATE, size=12,
                        weight=ft.FontWeight.W_600, expand=True),
                ft.Icon(ft.Icons.REFRESH, color=C.LATE, size=16),
            ],
            spacing=8,
        ),
    )
