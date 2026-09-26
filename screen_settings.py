"""SettingsScreen — port dari App.js. Baris lain masih placeholder.
'Penyimpanan & Backup' konek ke backend, dan sekarang ada kartu 'URL Backend'
untuk ganti BASE_URL langsung dari dalam app (tersimpan permanen di HP,
tidak perlu build ulang APK tiap kali domain ngrok berubah)."""

import flet as ft
import theme as C
import api

ROWS = [
    ("notifications_outline", "Pengaturan Notifikasi"),
    ("schedule_outline", "Jam Kerja & Keterlambatan"),
    ("router_outline", "Kelola Perangkat RFID"),
    ("finger_outline", "Kelola Data Sidik Jari"),
    ("cloud_outline", "Penyimpanan & Backup"),
    ("person_outline", "Akun"),
    ("logout", "Keluar"),
]

_ICON_MAP = {
    "notifications_outline": ft.Icons.NOTIFICATIONS_OUTLINED,
    "schedule_outline": ft.Icons.SCHEDULE_OUTLINED,
    "router_outline": ft.Icons.ROUTER_OUTLINED,
    "finger_outline": ft.Icons.FINGERPRINT_OUTLINED,
    "cloud_outline": ft.Icons.CLOUD_OUTLINED,
    "person_outline": ft.Icons.PERSON_OUTLINE,
    "logout": ft.Icons.LOGOUT_OUTLINED,
}


def _build_base_url_card(page: ft.Page) -> ft.Container:
    url_field = ft.TextField(
        value=api.get_base_url(),
        hint_text="https://xxxx.ngrok-free.dev",
        color=C.TEXT,
        bgcolor=C.SURFACE_ALT,
        border_color=C.BORDER,
        content_padding=ft.Padding.symmetric(horizontal=12, vertical=10),
    )
    status_text = ft.Text("", size=12)

    async def save_url(e):
        url = (url_field.value or "").strip()
        if not (url.startswith("http://") or url.startswith("https://")):
            status_text.value = "URL harus diawali http:// atau https://"
            status_text.color = C.DANGER
            status_text.update()
            return

        await api.save_base_url(page, url)
        url_field.value = api.get_base_url()
        status_text.value = "Tersimpan. Data berikutnya diambil dari URL ini."
        status_text.color = C.SUCCESS
        status_text.update()
        url_field.update()

    def reset_default(e):
        url_field.value = api.DEFAULT_BASE_URL
        status_text.value = ""
        url_field.update()
        status_text.update()

    return ft.Container(
        bgcolor=C.SURFACE,
        border=ft.Border.all(1, C.BORDER),
        border_radius=ft.BorderRadius.all(14),
        padding=ft.Padding.all(16),
        margin=ft.Margin.only(bottom=16),
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.LINK, color=C.ACCENT, size=20),
                        ft.Text("URL Backend (ngrok)", color=C.TEXT, size=15, weight=ft.FontWeight.BOLD),
                    ],
                    spacing=8,
                ),
                ft.Text(
                    "Ganti kalau URL ngrok backend berubah — tersimpan di HP ini, "
                    "tidak perlu build ulang APK.",
                    color=C.TEXT_DIM,
                    size=12,
                ),
                url_field,
                status_text,
                ft.Row(
                    [
                        ft.Container(
                            content=ft.Text("Simpan", color=C.BG, weight=ft.FontWeight.BOLD),
                            bgcolor=C.ACCENT,
                            border_radius=ft.BorderRadius.all(10),
                            padding=ft.Padding.symmetric(vertical=12),
                            alignment=ft.Alignment.CENTER,
                            expand=True,
                            on_click=lambda e: page.run_task(save_url, e),
                        ),
                        ft.Container(
                            content=ft.Text("Reset", color=C.TEXT_DIM, weight=ft.FontWeight.W_600),
                            bgcolor=C.SURFACE_ALT,
                            border=ft.Border.all(1, C.BORDER),
                            border_radius=ft.BorderRadius.all(10),
                            padding=ft.Padding.symmetric(vertical=12, horizontal=16),
                            alignment=ft.Alignment.CENTER,
                            on_click=reset_default,
                        ),
                    ],
                    spacing=10,
                ),
            ],
            spacing=8,
        ),
    )


def build_settings_view(page: ft.Page, on_logout) -> ft.Control:
    def open_account_dialog(e):
        current_field = ft.TextField(
            label="Password saat ini", password=True, can_reveal_password=True,
            color=C.TEXT, bgcolor=C.SURFACE_ALT, border_color=C.BORDER,
        )
        new_field = ft.TextField(
            label="Password baru (min. 6 karakter)", password=True, can_reveal_password=True,
            color=C.TEXT, bgcolor=C.SURFACE_ALT, border_color=C.BORDER,
        )
        status_text = ft.Text("", size=12)

        async def submit_change_password(e):
            current = current_field.value or ""
            new = new_field.value or ""
            if not current or not new:
                status_text.value = "Isi kedua kolom dulu."
                status_text.color = C.DANGER
                status_text.update()
                return
            try:
                await api.change_password(current, new)
                status_text.value = "Password diganti. Silakan login lagi."
                status_text.color = C.SUCCESS
                status_text.update()
                await api.force_logout()  # server sudah mencabut semua sesi lama
                page.pop_dialog()
                on_logout()
            except Exception as ex:
                status_text.value = f"Gagal: {ex}"
                status_text.color = C.DANGER
                status_text.update()

        dialog = ft.AlertDialog(
            title=ft.Text("Akun", color=C.TEXT),
            bgcolor=C.SURFACE,
            content=ft.Column(
                [
                    ft.Row(
                        [ft.Icon(ft.Icons.PERSON, color=C.ACCENT, size=20),
                         ft.Text(api.get_username() or "-", color=C.TEXT, size=15, weight=ft.FontWeight.BOLD)],
                        spacing=8,
                    ),
                    ft.Divider(color=C.BORDER),
                    ft.Text("Ganti Password", color=C.TEXT_DIM, size=12, weight=ft.FontWeight.W_600),
                    current_field,
                    new_field,
                    status_text,
                ],
                tight=True,
                spacing=10,
            ),
            actions=[
                ft.TextButton(content=ft.Text("Tutup", color=C.TEXT_DIM), on_click=lambda e: page.pop_dialog()),
                ft.ElevatedButton(
                    content=ft.Text("Simpan Password Baru"), bgcolor=C.ACCENT, color=C.BG,
                    on_click=lambda e: page.run_task(submit_change_password, e),
                ),
            ],
        )
        page.show_dialog(dialog)

    def open_logout_dialog(e):
        async def confirm(e):
            page.pop_dialog()
            await api.logout()
            on_logout()

        dialog = ft.AlertDialog(
            title=ft.Text("Keluar", color=C.TEXT),
            bgcolor=C.SURFACE,
            content=ft.Text(f"Keluar dari akun {api.get_username() or ''}?", color=C.TEXT_DIM),
            actions=[
                ft.TextButton(content=ft.Text("Batal", color=C.TEXT_DIM), on_click=lambda e: page.pop_dialog()),
                ft.TextButton(content=ft.Text("Keluar", color=C.DANGER), on_click=lambda e: page.run_task(confirm, e)),
            ],
        )
        page.show_dialog(dialog)

    async def open_notifications_dialog(e):
        try:
            current = await api.fetch_notification_settings()
        except Exception as ex:
            print("Gagal ambil pengaturan notifikasi, pakai default:", ex)
            current = {"rfid_unknown": True, "late_attendance": True, "camera_offline": True}

        status_text = ft.Text("", size=12)

        switch_rfid = ft.Switch(value=current.get("rfid_unknown", True), active_color=C.ACCENT)
        switch_late = ft.Switch(value=current.get("late_attendance", True), active_color=C.ACCENT)
        switch_camera = ft.Switch(value=current.get("camera_offline", True), active_color=C.ACCENT)

        def make_toggle_handler(key: str, switch: ft.Switch):
            async def handler(e):
                try:
                    await api.update_notification_settings(**{key: switch.value})
                    status_text.value = "Tersimpan"
                    status_text.color = C.SUCCESS
                except Exception as ex:
                    status_text.value = f"Gagal menyimpan: {ex}"
                    status_text.color = C.DANGER
                status_text.update()
            return handler

        switch_rfid.on_change = lambda e: page.run_task(make_toggle_handler("rfid_unknown", switch_rfid), e)
        switch_late.on_change = lambda e: page.run_task(make_toggle_handler("late_attendance", switch_late), e)
        switch_camera.on_change = lambda e: page.run_task(make_toggle_handler("camera_offline", switch_camera), e)

        def notif_row(icon, label: str, switch: ft.Switch, note: str | None = None) -> ft.Column:
            children = [
                ft.Row(
                    [
                        ft.Icon(icon, size=18, color=C.TEXT_DIM),
                        ft.Text(label, color=C.TEXT, size=14, expand=True),
                        switch,
                    ],
                    spacing=10,
                ),
            ]
            if note:
                children.append(ft.Text(note, color=C.TEXT_DIM, size=11))
            return ft.Column(children, spacing=2)

        dialog = ft.AlertDialog(
            title=ft.Text("Pengaturan Notifikasi", color=C.TEXT),
            bgcolor=C.SURFACE,
            content=ft.Column(
                [
                    notif_row(ft.Icons.CREDIT_CARD_OFF_OUTLINED, "Kartu RFID tidak dikenal", switch_rfid),
                    notif_row(ft.Icons.SCHEDULE_OUTLINED, "Absen terlambat", switch_late),
                    notif_row(
                        ft.Icons.SENSORS_OFF_OUTLINED,
                        "Perangkat scan offline",
                        switch_camera,
                        note="Aktif setelah reader/sensor tambahan (wajah, sidik jari) terpasang",
                    ),
                    status_text,
                ],
                tight=True,
                spacing=14,
            ),
            actions=[
                ft.TextButton(content=ft.Text("Tutup", color=C.TEXT_DIM), on_click=lambda e: page.pop_dialog()),
            ],
        )
        page.show_dialog(dialog)

    async def open_general_settings_dialog(e):
        try:
            current = await api.fetch_general_settings()
        except Exception as ex:
            print("Gagal ambil pengaturan umum, pakai default:", ex)
            current = {"jam_masuk_batas": "08:00"}

        jam_field = ft.TextField(
            value=current.get("jam_masuk_batas", "08:00"), label="Jam batas masuk (format 24 jam, HH:mm)",
            hint_text="08:00", color=C.TEXT, bgcolor=C.SURFACE_ALT, border_color=C.BORDER,
            content_padding=ft.Padding.symmetric(horizontal=12, vertical=10),
        )
        status_text = ft.Text("", size=12)

        async def save(ev):
            value = (jam_field.value or "").strip()
            try:
                await api.update_general_settings(jam_masuk_batas=value)
                status_text.value = "Tersimpan — berlaku untuk scan berikutnya."
                status_text.color = C.SUCCESS
            except Exception as ex:
                status_text.value = f"Gagal: {ex}"
                status_text.color = C.DANGER
            status_text.update()

        dialog = ft.AlertDialog(
            title=ft.Text("Jam Kerja & Keterlambatan", color=C.TEXT),
            bgcolor=C.SURFACE,
            content=ft.Column(
                [
                    ft.Text(
                        "Scan 'masuk' setelah jam ini otomatis ditandai Terlambat. "
                        "Berlaku untuk semua reader RFID.",
                        color=C.TEXT_DIM, size=12,
                    ),
                    jam_field,
                    status_text,
                ],
                tight=True, spacing=10,
            ),
            actions=[
                ft.TextButton(content=ft.Text("Tutup", color=C.TEXT_DIM), on_click=lambda e: page.pop_dialog()),
                ft.ElevatedButton(
                    content=ft.Text("Simpan"), bgcolor=C.ACCENT, color=C.BG,
                    on_click=lambda e: page.run_task(save, e),
                ),
            ],
        )
        page.show_dialog(dialog)

    async def open_device_management_dialog(e):
        """Daftar reader RFID (ESP32) yang pernah online. Tiap device bisa
        diedit reader_id/broker MQTT-nya di sini -- perubahan langsung
        dikirim ke device lewat MQTT (topic config/<mac>/reload), device
        auto-restart & pakai config baru. Tidak perlu reflash firmware."""
        list_col = ft.Column(spacing=10)
        loading = ft.Container(content=ft.ProgressRing(color=C.ACCENT), alignment=ft.Alignment.CENTER, padding=ft.Padding.all(20))
        list_col.controls.append(loading)

        dialog = ft.AlertDialog(
            title=ft.Text("Kelola Perangkat RFID", color=C.TEXT),
            bgcolor=C.SURFACE,
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Text(
                            "Reader yang pernah terhubung. Ganti Reader ID atau broker MQTT "
                            "di sini -- device akan otomatis reload config-nya sendiri.",
                            color=C.TEXT_DIM, size=12,
                        ),
                        ft.Divider(color=C.BORDER),
                        list_col,
                    ],
                    tight=True, spacing=10, scroll=ft.ScrollMode.AUTO,
                ),
                width=340, height=420,
            ),
            actions=[ft.TextButton(content=ft.Text("Tutup", color=C.TEXT_DIM), on_click=lambda e: page.pop_dialog())],
        )
        page.show_dialog(dialog)

        def device_card(dev: dict) -> ft.Container:
            mac = dev["mac"]
            reader_field = ft.TextField(
                value=dev.get("reader_id", ""), label="Reader ID",
                color=C.TEXT, bgcolor=C.SURFACE_ALT, border_color=C.BORDER, text_size=13,
                content_padding=ft.Padding.symmetric(horizontal=10, vertical=8),
            )
            host_field = ft.TextField(
                value=dev.get("mqtt_host") or "", label="Override broker MQTT (kosongkan = default)",
                color=C.TEXT, bgcolor=C.SURFACE_ALT, border_color=C.BORDER, text_size=13,
                content_padding=ft.Padding.symmetric(horizontal=10, vertical=8),
            )
            port_field = ft.TextField(
                value=str(dev.get("mqtt_port") or ""), label="Port", width=90,
                color=C.TEXT, bgcolor=C.SURFACE_ALT, border_color=C.BORDER, text_size=13,
                content_padding=ft.Padding.symmetric(horizontal=10, vertical=8),
            )
            cooldown_field = ft.TextField(
                value=str(dev.get("scan_cooldown_ms") or 3000), label="Jeda anti-scan-ganda (ms)",
                color=C.TEXT, bgcolor=C.SURFACE_ALT, border_color=C.BORDER, text_size=13,
                content_padding=ft.Padding.symmetric(horizontal=10, vertical=8),
            )
            buzzer_switch = ft.Switch(
                value=bool(dev.get("buzzer_enabled", 1)), active_color=C.ACCENT, label="Buzzer aktif",
                label_style=ft.TextStyle(color=C.TEXT_DIM, size=12),
            )
            card_status = ft.Text("", size=11)
            last_seen = dev.get("last_seen_at") or "-"

            async def save(ev, mac=mac, reader_field=reader_field, host_field=host_field,
                           port_field=port_field, cooldown_field=cooldown_field,
                           buzzer_switch=buzzer_switch, card_status=card_status):
                card_status.value = "Menyimpan..."
                card_status.color = C.TEXT_DIM
                card_status.update()
                try:
                    port_val = port_field.value.strip()
                    cooldown_val = cooldown_field.value.strip()
                    await api.update_device(
                        mac,
                        reader_id=reader_field.value.strip(),
                        mqtt_host=host_field.value.strip(),
                        mqtt_port=int(port_val) if port_val else "",
                        scan_cooldown_ms=int(cooldown_val) if cooldown_val else 3000,
                        buzzer_enabled=buzzer_switch.value,
                    )
                    card_status.value = "Tersimpan — device akan reload otomatis"
                    card_status.color = C.SUCCESS
                except Exception as ex:
                    card_status.value = f"Gagal: {ex}"
                    card_status.color = C.DANGER
                card_status.update()

            return ft.Container(
                bgcolor=C.SURFACE_ALT, border=ft.Border.all(1, C.BORDER), border_radius=ft.BorderRadius.all(12),
                padding=ft.Padding.all(12),
                content=ft.Column(
                    [
                        ft.Row(
                            [ft.Icon(ft.Icons.NFC_ROUNDED, color=C.RFID, size=16),
                             ft.Text(mac, color=C.TEXT_DIM, size=11, font_family="monospace", expand=True),
                             ft.Text(f"terakhir online: {last_seen[:16] if last_seen != '-' else '-'}", color=C.TEXT_FAINT, size=10)],
                            spacing=6,
                        ),
                        reader_field,
                        ft.Row([host_field, port_field], spacing=8),
                        cooldown_field,
                        buzzer_switch,
                        ft.Row(
                            [
                                ft.Container(
                                    content=ft.Text("Simpan", color=C.BG, size=12, weight=ft.FontWeight.BOLD),
                                    bgcolor=C.ACCENT, border_radius=ft.BorderRadius.all(8),
                                    padding=ft.Padding.symmetric(vertical=8), alignment=ft.Alignment.CENTER,
                                    expand=True, on_click=lambda ev: page.run_task(save, ev),
                                ),
                                card_status,
                            ],
                            spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    ],
                    spacing=8,
                ),
            )

        try:
            devices = await api.fetch_devices()
        except Exception as ex:
            list_col.controls = [ft.Text(f"Gagal mengambil daftar perangkat: {ex}", color=C.DANGER, size=13)]
            list_col.update()
            return

        list_col.controls.clear()
        if not devices:
            list_col.controls.append(
                ft.Text(
                    "Belum ada reader yang pernah online. Nyalakan ESP32 & sambungkan "
                    "ke WiFi lewat mode setup-nya, reader akan otomatis muncul di sini.",
                    color=C.TEXT_DIM, size=13,
                )
            )
        for dev in devices:
            list_col.controls.append(device_card(dev))
        list_col.update()

    def open_backup_dialog(e):
        def do_backup(e):
            page.pop_dialog()
            page.launch_url(api.backup_url())

        def do_export(e):
            page.pop_dialog()
            page.launch_url(api.attendance_export_url())

        dialog = ft.AlertDialog(
            title=ft.Text("Backup & Export Data Absensi", color=C.TEXT),
            bgcolor=C.SURFACE,
            content=ft.Text("Pilih file yang ingin diunduh:", color=C.TEXT_DIM),
            actions=[
                ft.TextButton(content=ft.Text("Backup Database (.db)", color=C.ACCENT), on_click=do_backup),
                ft.TextButton(content=ft.Text("Export Laporan (.csv)", color=C.ACCENT), on_click=do_export),
                ft.TextButton(content=ft.Text("Batal", color=C.TEXT_DIM), on_click=lambda e: page.pop_dialog()),
            ],
        )
        page.show_dialog(dialog)

    def open_placeholder_dialog(title: str, message: str):
        def opener(e):
            dialog = ft.AlertDialog(
                title=ft.Text(title, color=C.TEXT),
                bgcolor=C.SURFACE,
                content=ft.Text(message, color=C.TEXT_DIM),
                actions=[ft.TextButton(content=ft.Text("Mengerti", color=C.ACCENT), on_click=lambda e: page.pop_dialog())],
            )
            page.show_dialog(dialog)
        return opener

    def handle_press(label: str):
        if label == "Penyimpanan & Backup":
            return open_backup_dialog
        if label == "Pengaturan Notifikasi":
            return lambda e: page.run_task(open_notifications_dialog, e)
        if label == "Jam Kerja & Keterlambatan":
            return lambda e: page.run_task(open_general_settings_dialog, e)
        if label == "Kelola Perangkat RFID":
            return lambda e: page.run_task(open_device_management_dialog, e)
        if label == "Kelola Data Sidik Jari":
            return open_placeholder_dialog(
                "Kelola Data Sidik Jari",
                "Fitur ini masih mode simulasi (lihat tab Scan > Sidik Jari). "
                "Pengelolaan data sidik jari asli akan aktif setelah sensor fisik terpasang.",
            )
        if label == "Akun":
            return open_account_dialog
        if label == "Keluar":
            return open_logout_dialog
        return lambda e: None  # baris lain masih placeholder

    rows = []
    for key, label in ROWS:
        rows.append(
            ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(_ICON_MAP[key], size=20, color=C.TEXT_DIM),
                        ft.Text(label, color=C.TEXT, size=15, expand=True),
                        ft.Icon(ft.Icons.CHEVRON_RIGHT, size=18, color=C.TEXT_DIM),
                    ],
                    spacing=12,
                ),
                bgcolor=C.SURFACE, border=ft.Border.all(1, C.BORDER), border_radius=ft.BorderRadius.all(12),
                padding=ft.Padding.all(14),
                on_click=handle_press(label),
            )
        )

    return ft.Container(
        bgcolor=C.BG,
        expand=True,
        padding=ft.Padding.only(top=16, left=16, right=16),
        content=ft.Column(
            [
                ft.Text("Pengaturan", size=22, weight=ft.FontWeight.BOLD, color=C.TEXT),
                ft.Text(f"Masuk sebagai {api.get_username() or '-'}", size=12, color=C.TEXT_DIM),
                ft.Container(height=8),
                ft.Container(
                    content=ft.ListView(
                        [_build_base_url_card(page)] + rows,
                        spacing=8,
                        expand=True,
                    ),
                    expand=True,
                ),
            ],
            expand=True,
        ),
    )