"""LiveScreen & HistoryScreen — masih data mock, sama seperti di App.js.
Nanti tinggal disambungkan ke stream ESP32-CAM / API rekaman kalau sudah ada."""

import flet as ft
import theme as C

CAMERAS = [
    {"id": "cam1", "name": "Depan Rumah", "location": "Teras", "online": True, "has_motion": True},
    {"id": "cam2", "name": "Garasi", "location": "Garasi", "online": True, "has_motion": False},
    {"id": "cam3", "name": "Halaman Belakang", "location": "Taman", "online": False, "has_motion": False},
]

RECORDINGS = [
    {"id": "r1", "camera": "Depan Rumah", "time": "27 Agu, 14:32", "duration": "00:45", "trigger": "motion"},
    {"id": "r2", "camera": "Garasi", "time": "27 Agu, 13:10", "duration": "02:10", "trigger": "manual"},
    {"id": "r3", "camera": "Depan Rumah", "time": "27 Agu, 09:05", "duration": "00:22", "trigger": "motion"},
    {"id": "r4", "camera": "Halaman Belakang", "time": "26 Agu, 22:47", "duration": "01:03", "trigger": "motion"},
]


def header(title: str, trailing: ft.Control | None = None) -> ft.Row:
    return ft.Row(
        [ft.Text(title, size=22, weight=ft.FontWeight.BOLD, color=C.TEXT)] + ([trailing] if trailing else []),
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )


def build_live_view() -> ft.Control:
    state = {"selected": CAMERAS[0]}

    video_box = ft.Container(
        height=220,
        border_radius=ft.BorderRadius.all(16),
        bgcolor=C.SURFACE,
        border=ft.Border.all(1, C.BORDER),
        alignment=ft.Alignment.CENTER,
        clip_behavior=ft.ClipBehavior.HARD_EDGE,
    )

    live_badge = ft.Container(
        content=ft.Row(
            [
                ft.Container(width=6, height=6, border_radius=ft.BorderRadius.all(3), bgcolor=C.DANGER),
                ft.Text("LIVE", size=11, weight=ft.FontWeight.BOLD, color=C.TEXT),
            ],
            spacing=6,
        ),
        bgcolor=ft.Colors.with_opacity(0.5, ft.Colors.BLACK),
        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
        border_radius=ft.BorderRadius.all(8),
        left=12,
        top=12,
    )

    camera_list = ft.ListView(spacing=10, padding=ft.Padding.symmetric(horizontal=16))

    def refresh_video():
        cam = state["selected"]
        if cam["online"]:
            content = ft.Column(
                [
                    ft.Icon(ft.Icons.VIDEOCAM, size=40, color=C.TEXT_DIM),
                    ft.Text(f"Stream: {cam['name']}", color=C.TEXT, size=15, weight=ft.FontWeight.W_600),
                    ft.Text("Belum terhubung ke ESP32-CAM", color=C.TEXT_DIM, size=12),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=6,
            )
        else:
            content = ft.Column(
                [
                    ft.Icon(ft.Icons.CLOUD_OFF_OUTLINED, size=40, color=C.DANGER),
                    ft.Text("Kamera Offline", color=C.DANGER, size=15, weight=ft.FontWeight.W_600),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=6,
            )
        video_box.content = ft.Stack([content, live_badge])

    def select_camera(cam):
        state["selected"] = cam
        refresh_video()
        refresh_camera_list()
        video_box.update()
        camera_list.update()

    def refresh_camera_list():
        camera_list.controls.clear()
        for cam in CAMERAS:
            selected = cam["id"] == state["selected"]["id"]
            row_children = [
                ft.Container(
                    width=8, height=8, border_radius=ft.BorderRadius.all(4),
                    bgcolor=C.SUCCESS if cam["online"] else C.DANGER,
                ),
                ft.Column(
                    [
                        ft.Text(cam["name"], color=C.TEXT, size=15, weight=ft.FontWeight.W_600),
                        ft.Text(cam["location"], color=C.TEXT_DIM, size=12),
                    ],
                    spacing=2,
                    expand=True,
                ),
            ]
            if cam["has_motion"]:
                row_children.append(
                    ft.Container(
                        content=ft.Text("Gerakan", color=C.LATE, size=11, weight=ft.FontWeight.W_600),
                        bgcolor="#3A2A1C",
                        border=ft.Border.all(1, "#8A5A2C"),
                        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                        border_radius=ft.BorderRadius.all(6),
                    )
                )
            camera_list.controls.append(
                ft.Container(
                    content=ft.Row(row_children, spacing=10, alignment=ft.MainAxisAlignment.START),
                    bgcolor=C.SURFACE,
                    border=ft.Border.all(1, C.ACCENT if selected else C.BORDER),
                    border_radius=ft.BorderRadius.all(12),
                    padding=ft.Padding.all(12),
                    on_click=lambda e, c=cam: select_camera(c),
                )
            )

    refresh_video()
    refresh_camera_list()

    controls_row = ft.Row(
        [
            ft.IconButton(icon=ft.Icons.ARROW_BACK_IOS_NEW, icon_color=C.TEXT),
            ft.Container(
                content=ft.Row(
                    [ft.Icon(ft.Icons.RADIO_BUTTON_ON, color=C.DANGER, size=22),
                     ft.Text("Rekam", color=C.TEXT, weight=ft.FontWeight.W_600)],
                    spacing=6,
                ),
                bgcolor=C.SURFACE_ALT,
                border=ft.Border.all(1, C.BORDER),
                border_radius=ft.BorderRadius.all(999),
                padding=ft.Padding.symmetric(horizontal=18, vertical=10),
            ),
            ft.IconButton(icon=ft.Icons.ARROW_FORWARD_IOS, icon_color=C.TEXT),
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=24,
    )

    return ft.Container(
        bgcolor=C.BG,
        expand=True,
        padding=ft.Padding.only(top=16, left=16, right=16, bottom=8),
        content=ft.Column(
            [
                header("Live View", ft.Icon(ft.Icons.NOTIFICATIONS_OUTLINED, color=C.TEXT, size=22)),
                ft.Container(height=8),
                video_box,
                controls_row,
                ft.Text(
                    "KAMERA KAMU", color=C.TEXT_DIM, size=13, weight=ft.FontWeight.W_600,
                ),
                ft.Container(height=4),
                ft.Container(content=camera_list, expand=True),
            ],
            expand=True,
        ),
    )


def build_history_view() -> ft.Control:
    rows = []
    for item in RECORDINGS:
        badge_bg, badge_border, badge_label = (
            ("#3A2A1C", "#8A5A2C", "Motion") if item["trigger"] == "motion"
            else ("#1C2A3A", "#2C5A8A", "Manual")
        )
        rows.append(
            ft.Container(
                content=ft.Row(
                    [
                        ft.Container(
                            width=48, height=48, border_radius=ft.BorderRadius.all(8),
                            bgcolor=C.SURFACE_ALT, alignment=ft.Alignment.CENTER,
                            content=ft.Icon(ft.Icons.PLAY_ARROW, color=C.TEXT, size=18),
                        ),
                        ft.Column(
                            [
                                ft.Text(item["camera"], color=C.TEXT, size=15, weight=ft.FontWeight.W_600),
                                ft.Text(f"{item['time']} · {item['duration']}", color=C.TEXT_DIM, size=12),
                            ],
                            spacing=2,
                            expand=True,
                        ),
                        ft.Container(
                            content=ft.Text(badge_label, color=C.TEXT, size=11, weight=ft.FontWeight.W_600),
                            bgcolor=badge_bg,
                            border=ft.Border.all(1, badge_border),
                            padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                            border_radius=ft.BorderRadius.all(6),
                        ),
                    ],
                    spacing=12,
                ),
                bgcolor=C.SURFACE,
                border=ft.Border.all(1, C.BORDER),
                border_radius=ft.BorderRadius.all(12),
                padding=ft.Padding.all(12),
            )
        )

    return ft.Container(
        bgcolor=C.BG,
        expand=True,
        padding=ft.Padding.only(top=16, left=16, right=16),
        content=ft.Column(
            [
                header("Riwayat Rekaman"),
                ft.Container(height=8),
                ft.Container(content=ft.ListView(rows, spacing=10, expand=True), expand=True),
            ],
            expand=True,
        ),
    )
