"""screen_face.py — Tab 'Wajah' pada layar Scan, versi REAL (bukan mock).
Pakai kamera laptop (OpenCV) buat live preview, pendaftaran wajah baru
(ambil beberapa sampel otomatis), dan pengenalan (cocokkan ke data
tersimpan lalu kirim absen lewat endpoint manual yang sudah ada di
server.js -- tidak perlu ubah backend sama sekali).

Kamera hanya dibuka selama tab ini aktif (dipanggil dari screen_scan.py
lewat start()/stop()), supaya tidak mengunci webcam terus-menerus."""

import asyncio
import time
import flet as ft
import theme as C
import api
from face_engine import FaceEngine, SAMPLES_PER_PERSON

RECOGNIZE_COOLDOWN_S = 30  # jeda sebelum orang yang sama bisa absen lagi via wajah
LOOP_INTERVAL_S = 0.12  # ~8 fps, cukup ringan buat laptop rata-rata


class FaceTab:
    def __init__(self, page: ft.Page):
        self.page = page
        self.engine = FaceEngine()

        self._active = False
        self._latest_frame = None
        self._latest_box = None
        self._last_sample_time = 0.0
        self._enroll_name: str | None = None
        self._enroll_target = SAMPLES_PER_PERSON
        self._enroll_progress_cb = None
        self._last_recognized: tuple[str, float] | None = None
        self._recognizing = False

        # ---- UI ----
        self.preview_img = ft.Container(
            height=220, bgcolor=C.WAJAH_SOFT, border=ft.Border.all(1.5, C.WAJAH),
            border_radius=ft.BorderRadius.all(18), alignment=ft.Alignment.CENTER,
            content=ft.Column(
                [ft.Icon(ft.Icons.CAMERA_ALT_OUTLINED, color=C.WAJAH, size=40),
                 ft.Text("Membuka kamera...", color=C.TEXT_DIM, size=12)],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8,
            ),
        )
        self.status_text = ft.Text("Arahkan wajah ke kamera", color=C.TEXT_DIM, size=12)

        self.scan_btn_text = ft.Text("Deteksi & Absen Sekarang", color=C.BG, weight=ft.FontWeight.BOLD)
        self.scan_btn = ft.Container(
            content=self.scan_btn_text, bgcolor=C.WAJAH, border_radius=ft.BorderRadius.all(10),
            padding=ft.Padding.symmetric(vertical=12), alignment=ft.Alignment.CENTER,
            on_click=lambda e: self.page.run_task(self._do_recognize),
        )

        self.enrolled_label = ft.Text("WAJAH TERDAFTAR", color=C.TEXT_DIM, size=12, weight=ft.FontWeight.W_600)
        self.enrolled_col = ft.Column(spacing=8)
        self.enrolled_empty = ft.Text("Belum ada wajah terdaftar", color=C.TEXT_DIM, size=13)

        self.add_face_btn = ft.Container(
            content=ft.Row(
                [ft.Icon(ft.Icons.ADD_ROUNDED, color=C.WAJAH, size=16),
                 ft.Text("Daftarkan Wajah Baru", color=C.WAJAH, size=13, weight=ft.FontWeight.W_600)],
                spacing=6, alignment=ft.MainAxisAlignment.CENTER,
            ),
            bgcolor=C.WAJAH_SOFT, border=ft.Border.all(1, C.WAJAH), border_radius=ft.BorderRadius.all(10),
            padding=ft.Padding.symmetric(vertical=10),
            on_click=self._open_enroll_dialog,
        )

        real_badge = ft.Container(
            content=ft.Row(
                [ft.Icon(ft.Icons.VIDEOCAM_ROUNDED, size=13, color=C.SUCCESS),
                 ft.Text("Kamera laptop aktif — pengenalan lokal via OpenCV", size=11, color=C.SUCCESS, weight=ft.FontWeight.W_600)],
                spacing=6, tight=True,
            ),
            bgcolor="#132A22", border_radius=ft.BorderRadius.all(999),
            padding=ft.Padding.symmetric(horizontal=12, vertical=6),
        )

        self.container = ft.Column(
            [
                real_badge,
                ft.Container(height=12),
                self.preview_img,
                ft.Container(height=8),
                self.status_text,
                ft.Container(height=8),
                self.scan_btn,
                ft.Container(height=20),
                self.enrolled_label,
                ft.Container(height=8),
                self.enrolled_col,
                self.enrolled_empty,
                ft.Container(height=10),
                self.add_face_btn,
            ],
            expand=True, scroll=ft.ScrollMode.AUTO,
        )

        self._refresh_enrolled_list()

    # ------------------------------------------------------------ lifecycle
    async def start(self):
        if self._active:
            return
        ok = await asyncio.to_thread(self.engine.open_camera)
        if not ok:
            self.status_text.value = "Gagal membuka kamera laptop (dipakai app lain? / izin kamera ditolak?)"
            self.status_text.color = C.DANGER
            self._safe_update(self.status_text)
            return
        self._active = True
        self.page.run_task(self._loop)

    def stop(self):
        self._active = False
        self._enroll_name = None
        self.engine.close_camera()

    def _safe_update(self, control):
        try:
            control.update()
        except Exception:
            pass

    # ------------------------------------------------------------ loop kamera
    async def _loop(self):
        while self._active:
            frame = await asyncio.to_thread(self.engine.read_frame)
            if frame is None:
                await asyncio.sleep(0.2)
                continue

            box = await asyncio.to_thread(self.engine.detect_largest_face, frame)
            self._latest_frame = frame
            self._latest_box = box

            b64 = await asyncio.to_thread(self.engine.frame_to_base64, frame, box)
            self.preview_img.content = ft.Image(
                src_base64=b64, fit=ft.ImageFit.COVER,
                border_radius=ft.BorderRadius.all(16), width=1000, height=220,
            )
            self._safe_update(self.preview_img)

            # auto-capture sampel kalau lagi mode enrollment
            if self._enroll_name and box is not None:
                now = time.time()
                if now - self._last_sample_time >= 0.35:
                    gray = await asyncio.to_thread(self.engine.crop_face_gray, frame, box)
                    count = await asyncio.to_thread(self.engine.add_sample, self._enroll_name, gray)
                    self._last_sample_time = now
                    if self._enroll_progress_cb:
                        self._enroll_progress_cb(count)
                    if count >= self._enroll_target:
                        self._enroll_name = None  # target tercapai, UI dialog yang lanjut training

            await asyncio.sleep(LOOP_INTERVAL_S)

    # ------------------------------------------------------------ deteksi & absen
    async def _do_recognize(self):
        if self._recognizing:
            return
        if self._latest_frame is None or self._latest_box is None:
            self.status_text.value = "Wajah belum terdeteksi di kamera. Pastikan wajah terlihat jelas."
            self.status_text.color = C.LATE
            self._safe_update(self.status_text)
            return
        if not self.engine.has_model():
            self.status_text.value = "Belum ada wajah terdaftar. Daftarkan wajah dulu lewat tombol di bawah."
            self.status_text.color = C.LATE
            self._safe_update(self.status_text)
            return

        self._recognizing = True
        self.scan_btn_text.value = "Mencocokkan..."
        self._safe_update(self.scan_btn)

        frame, box = self._latest_frame, self._latest_box
        gray = await asyncio.to_thread(self.engine.crop_face_gray, frame, box)
        name, distance = await asyncio.to_thread(self.engine.predict, gray)

        if name:
            now = time.time()
            last = self._last_recognized
            if last and last[0] == name and (now - last[1]) < RECOGNIZE_COOLDOWN_S:
                sisa = int(RECOGNIZE_COOLDOWN_S - (now - last[1]))
                self.status_text.value = f"{name} sudah tercatat barusan. Coba lagi {sisa} detik lagi."
                self.status_text.color = C.TEXT_DIM
            else:
                try:
                    await api.post_manual_attendance(name)
                    self._last_recognized = (name, now)
                    self.status_text.value = f"✓ Absen tercatat untuk {name} (jarak {distance:.0f})"
                    self.status_text.color = C.SUCCESS
                except Exception as ex:
                    self.status_text.value = f"Wajah dikenali ({name}) tapi gagal simpan absen: {ex}"
                    self.status_text.color = C.DANGER
        else:
            self.status_text.value = f"Wajah tidak dikenali (jarak {distance:.0f}). Coba lagi atau daftarkan wajah baru."
            self.status_text.color = C.LATE

        self.scan_btn_text.value = "Deteksi & Absen Sekarang"
        self._safe_update(self.scan_btn)
        self._safe_update(self.status_text)
        self._recognizing = False

    # ------------------------------------------------------------ enrollment dialog
    def _open_enroll_dialog(self, e):
        name_field = ft.TextField(
            hint_text="Nama lengkap", color=C.TEXT, bgcolor=C.SURFACE_ALT, border_color=C.BORDER,
            content_padding=ft.Padding.symmetric(horizontal=12, vertical=10),
        )
        progress_text = ft.Text(f"Sampel: 0/{self._enroll_target}", color=C.TEXT_DIM, size=13)
        hint_text = ft.Text(
            "Pastikan wajah terlihat jelas & pencahayaan cukup. Gerakkan kepala sedikit "
            "(kiri/kanan/atas/bawah) selama pengambilan sampel supaya modelnya lebih akurat.",
            color=C.TEXT_DIM, size=11,
        )

        start_btn = ft.TextButton(content=ft.Text("Mulai Ambil Sampel", color=C.WAJAH, weight=ft.FontWeight.W_600))
        finish_btn = ft.TextButton(content=ft.Text("Selesai & Latih", color=C.SUCCESS, weight=ft.FontWeight.W_600), disabled=True)
        cancel_btn = ft.TextButton(content=ft.Text("Batal", color=C.TEXT_DIM))

        def on_progress(count):
            progress_text.value = f"Sampel: {count}/{self._enroll_target}"
            finish_btn.disabled = count < 5
            self._safe_update(progress_text)
            self._safe_update(finish_btn)
            if count >= self._enroll_target:
                self.page.run_task(do_finish, None)

        self._enroll_progress_cb = on_progress

        def do_start(e):
            name = (name_field.value or "").strip()
            if not name:
                name_field.error_text = "Isi nama dulu"
                self._safe_update(name_field)
                return
            self._enroll_name = name
            self._last_sample_time = 0
            start_btn.disabled = True
            name_field.disabled = True
            self._safe_update(start_btn)
            self._safe_update(name_field)

        async def do_finish(e):
            self._enroll_progress_cb = None
            self._enroll_name = None
            name = (name_field.value or "").strip()
            if name and self.engine.sample_count(name) >= 1:
                await asyncio.to_thread(self.engine.train)
                self._refresh_enrolled_list()
                self._show_snack(f"Wajah '{name}' terdaftar & model dilatih ulang.")
            self.page.pop_dialog()

        def do_cancel(e):
            self._enroll_progress_cb = None
            self._enroll_name = None
            self.page.pop_dialog()

        start_btn.on_click = do_start
        finish_btn.on_click = lambda e: self.page.run_task(do_finish, e)
        cancel_btn.on_click = do_cancel

        dialog = ft.AlertDialog(
            title=ft.Text("Daftarkan Wajah Baru", color=C.TEXT),
            bgcolor=C.SURFACE,
            content=ft.Column(
                [name_field, hint_text, progress_text],
                tight=True, spacing=10, width=300,
            ),
            actions=[cancel_btn, start_btn, finish_btn],
        )
        self.page.show_dialog(dialog)

    # ------------------------------------------------------------ list & delete
    def _refresh_enrolled_list(self):
        people = self.engine.list_people()
        self.enrolled_label.value = f"WAJAH TERDAFTAR ({len(people)})"
        self.enrolled_empty.visible = len(people) == 0

        rows = []
        for p in people:
            rows.append(
                ft.Container(
                    bgcolor=C.SURFACE, border=ft.Border.all(1, C.BORDER), border_radius=ft.BorderRadius.all(12),
                    padding=ft.Padding.all(12),
                    content=ft.Row(
                        [
                            ft.Container(
                                content=ft.Icon(ft.Icons.PERSON_ROUNDED, color=C.WAJAH, size=18),
                                width=36, height=36, border_radius=ft.BorderRadius.all(18),
                                bgcolor=C.WAJAH_SOFT, alignment=ft.Alignment.CENTER,
                            ),
                            ft.Column(
                                [ft.Text(p["name"], color=C.TEXT, size=14, weight=ft.FontWeight.W_600),
                                 ft.Text(f"{p['samples']} sampel", color=C.TEXT_DIM, size=11)],
                                spacing=2, expand=True,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE, icon_color=C.DANGER, icon_size=18,
                                on_click=lambda e, n=p["name"]: self._confirm_delete(n),
                            ),
                        ],
                        spacing=10,
                    ),
                )
            )
        self.enrolled_col.controls = rows
        self._safe_update(self.enrolled_col)
        self._safe_update(self.enrolled_label)
        self._safe_update(self.enrolled_empty)

    def _confirm_delete(self, name: str):
        def do_delete(e):
            self.page.pop_dialog()
            self.engine.delete_person(name)
            self._refresh_enrolled_list()
            self._show_snack(f"Wajah '{name}' dihapus.")

        dialog = ft.AlertDialog(
            title=ft.Text("Hapus Wajah", color=C.TEXT), bgcolor=C.SURFACE,
            content=ft.Text(f"Hapus semua data wajah milik {name}?", color=C.TEXT_DIM),
            actions=[
                ft.TextButton(content=ft.Text("Batal", color=C.TEXT_DIM), on_click=lambda e: self.page.pop_dialog()),
                ft.TextButton(content=ft.Text("Hapus", color=C.DANGER), on_click=do_delete),
            ],
        )
        self.page.show_dialog(dialog)

    def _show_snack(self, text: str):
        snack = ft.SnackBar(content=ft.Text(text))
        if hasattr(self.page, "overlay"):
            self.page.overlay.append(snack)
        try:
            snack.open = True
        except Exception:
            pass
        self.page.update()
