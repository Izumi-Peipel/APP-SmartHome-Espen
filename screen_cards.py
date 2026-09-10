"""RegisterCardScreen — port dari RegisterCardScreen.js.
Poll kartu baru yang belum terdaftar tiap 3 detik, daftarkan, dan kelola
daftar kartu yang sudah terdaftar."""

import asyncio
import flet as ft
import theme as C
import api

POLL_INTERVAL_S = 3


class CardsView:
    def __init__(self, page: ft.Page):
        self.page = page
        self.pending_card: dict | None = None
        self.cards: list[dict] = []
        self.loading_cards = True
        self.submitting = False
        self._running = False

        self.name_input = ft.TextField(
            hint_text="Nama pemilik kartu", color=C.TEXT, bgcolor=C.SURFACE_ALT,
            border_color=C.BORDER, content_padding=ft.Padding.symmetric(horizontal=12, vertical=10),
        )

        self.pending_area = ft.Container()
        self.cards_label = ft.Text("KARTU TERDAFTAR (0)", color=C.TEXT_DIM, size=13, weight=ft.FontWeight.W_600)
        self.cards_list = ft.ListView(spacing=10, expand=True)
        self.cards_empty = ft.Container(
            content=ft.Column(
                [ft.Icon(ft.Icons.BADGE_OUTLINED, size=32, color=C.TEXT_DIM),
                 ft.Text("Belum ada kartu terdaftar", color=C.TEXT_DIM)],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            alignment=ft.Alignment.CENTER, expand=True, visible=False,
        )
        self.cards_loading = ft.Container(content=ft.ProgressRing(color=C.ACCENT), alignment=ft.Alignment.CENTER, expand=True)
        self.cards_area = ft.Stack([self.cards_list, self.cards_empty, self.cards_loading], expand=True)

        self.cards_header = ft.Row(
            [
                self.cards_label,
                ft.IconButton(
                    icon=ft.Icons.REFRESH,
                    icon_color=C.TEXT_DIM,
                    icon_size=18,
                    tooltip="Muat ulang",
                    on_click=lambda e: self.page.run_task(self._on_pull_refresh, e),
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        self.container = ft.Container(
            bgcolor=C.BG,
            expand=True,
            padding=ft.Padding.only(top=16, left=16, right=16, bottom=8),
            content=ft.Column(
                [
                    ft.Text("Kartu RFID", size=22, weight=ft.FontWeight.BOLD, color=C.TEXT),
                    ft.Container(height=8),
                    self.pending_area,
                    self.cards_header,
                    ft.Container(height=4),
                    self.cards_area,
                ],
                expand=True,
            ),
        )

        self._render_pending()

    # ---------------------------------------------------------------- data
    async def _on_pull_refresh(self, e):
        # Dipanggil dari tombol refresh manual di header daftar kartu.
        await asyncio.gather(self.fetch_cards(), self.fetch_pending_card())

    async def fetch_cards(self):
        try:
            self.cards = await api.fetch_cards()
        except Exception as ex:
            print("Gagal ambil daftar kartu:", ex)
        finally:
            self.loading_cards = False
            self._render_cards()
            try:
                self.container.update()
            except Exception:
                pass

    async def fetch_pending_card(self):
        try:
            new_pending = await api.fetch_pending_card()
        except Exception as ex:
            print("Gagal cek kartu baru:", ex)
            return

        old_uid = self.pending_card.get("uid") if self.pending_card else None
        new_uid = new_pending.get("uid") if new_pending else None

        if new_uid == old_uid:
            # Tidak ada perubahan (masih kartu pending yang sama, atau
            # sama-sama kosong) -> JANGAN sentuh UI. Kalau tetap di-render
            # ulang tiap poll, kotak isian nama akan dibuat ulang dan
            # kehilangan fokus/isian persis saat user sedang mengetik.
            return

        if new_uid:
            self.page.run_task(self._notify_unknown_card, new_uid)

        self.pending_card = new_pending
        self._render_pending()
        try:
            self.pending_area.update()
        except Exception:
            pass

    async def _notify_unknown_card(self, uid: str):
        try:
            settings = await api.fetch_notification_settings()
        except Exception as ex:
            print("Gagal cek pengaturan notifikasi, tampilkan default:", ex)
            settings = {"rfid_unknown": True}

        if settings.get("rfid_unknown", True):
            self._show_snack(f"Kartu tidak dikenal terdeteksi: {uid}")

    async def start(self):
        if self._running:
            return
        self._running = True
        await asyncio.gather(self.fetch_cards(), self.fetch_pending_card())
        self.page.run_task(self._poll_loop)

    async def _poll_loop(self):
        while self._running:
            await asyncio.sleep(POLL_INTERVAL_S)
            await self.fetch_pending_card()

    # ---------------------------------------------------------------- actions
    async def _submit_register(self, e):
        if not self.pending_card:
            return
        name = (self.name_input.value or "").strip()
        if not name:
            self._show_snack("Isi nama pemilik kartu dulu.")
            return
        self.submitting = True
        self._render_pending()
        self.pending_area.update()
        try:
            data = await api.register_card(self.pending_card["uid"], name)
            self.name_input.value = ""
            self.pending_card = None
            await self.fetch_cards()
            self._show_snack(f"Kartu terdaftar atas nama {data.get('name', name)}")
        except Exception as ex:
            self._show_snack(f"Gagal: {ex}")
        finally:
            self.submitting = False
            self._render_pending()
            self.pending_area.update()

    def _delete_card(self, uid: str, name: str):
        async def confirm(e):
            self.page.pop_dialog()
            try:
                await api.delete_card(uid)
            except Exception as ex:
                self._show_snack(f"Gagal menghapus kartu: {ex}")
                return
            try:
                await self.fetch_cards()
            except Exception as ex:
                print("Kartu terhapus, tapi gagal refresh daftar:", ex)
                self._show_snack("Kartu berhasil dihapus (daftar akan update sebentar lagi)")

        dialog = ft.AlertDialog(
            title=ft.Text("Hapus Kartu", color=C.TEXT),
            bgcolor=C.SURFACE,
            content=ft.Text(f"Hapus kartu milik {name}?", color=C.TEXT_DIM),
            actions=[
                ft.TextButton(content=ft.Text("Batal", color=C.TEXT_DIM), on_click=lambda e: self.page.pop_dialog()),
                ft.TextButton(content=ft.Text("Hapus", color=C.DANGER), on_click=lambda e: self.page.run_task(confirm, e)),
            ],
        )
        self.page.show_dialog(dialog)

    def _show_snack(self, text: str):
        self.page.show_dialog  # no-op reference to keep linter happy
        snack = ft.SnackBar(content=ft.Text(text))
        self.page.overlay.append(snack) if hasattr(self.page, "overlay") else None
        try:
            snack.open = True
        except Exception:
            pass
        self.page.update()

    # ---------------------------------------------------------------- render
    def _render_pending(self):
        if self.pending_card:
            submit_content = (
                ft.ProgressRing(color=C.BG, width=16, height=16, stroke_width=2)
                if self.submitting else ft.Text("Daftarkan Kartu", color=C.BG, weight=ft.FontWeight.BOLD)
            )
            self.pending_area.content = ft.Container(
                bgcolor=C.SURFACE, border=ft.Border.all(1, C.ACCENT), border_radius=ft.BorderRadius.all(14),
                padding=ft.Padding.all(16), margin=ft.Margin.only(bottom=16),
                content=ft.Column(
                    [
                        ft.Row(
                            [ft.Icon(ft.Icons.CREDIT_CARD, color=C.ACCENT, size=22),
                             ft.Text("Kartu baru terdeteksi", color=C.TEXT, size=15, weight=ft.FontWeight.BOLD)],
                            spacing=8,
                        ),
                        ft.Text(self.pending_card.get("uid", ""), color=C.TEXT_DIM, size=13, font_family="monospace"),
                        self.name_input,
                        ft.Container(
                            content=submit_content, bgcolor=C.ACCENT, border_radius=ft.BorderRadius.all(10),
                            padding=ft.Padding.symmetric(vertical=12), alignment=ft.Alignment.CENTER,
                            on_click=None if self.submitting else lambda e: self.page.run_task(self._submit_register, e),
                        ),
                    ],
                    spacing=8,
                ),
            )
        else:
            self.pending_area.content = ft.Container(
                bgcolor=C.SURFACE, border=ft.Border.all(1, C.BORDER), border_radius=ft.BorderRadius.all(14),
                padding=ft.Padding.all(20), margin=ft.Margin.only(bottom=16),
                content=ft.Column(
                    [
                        ft.Icon(ft.Icons.DOCUMENT_SCANNER_OUTLINED, size=28, color=C.TEXT_DIM),
                        ft.Text(
                            "Tempelkan kartu baru ke reader untuk mendaftarkannya",
                            color=C.TEXT_DIM, size=13, text_align=ft.TextAlign.CENTER,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8,
                ),
            )

    def _render_cards(self):
        self.cards_label.value = f"KARTU TERDAFTAR ({len(self.cards)})"
        self.cards_loading.visible = self.loading_cards
        self.cards_empty.visible = (not self.loading_cards) and len(self.cards) == 0
        self.cards_list.visible = (not self.loading_cards) and len(self.cards) > 0

        rows = []
        for item in self.cards:
            rows.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Column(
                                [
                                    ft.Text(item["name"], color=C.TEXT, size=15, weight=ft.FontWeight.W_600),
                                    ft.Text(item["uid"], color=C.TEXT_DIM, size=12, font_family="monospace"),
                                ],
                                spacing=2, expand=True,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE, icon_color=C.DANGER,
                                on_click=lambda e, u=item["uid"], n=item["name"]: self._delete_card(u, n),
                            ),
                        ],
                    ),
                    bgcolor=C.SURFACE, border=ft.Border.all(1, C.BORDER), border_radius=ft.BorderRadius.all(12),
                    padding=ft.Padding.all(14),
                )
            )
        self.cards_list.controls = rows