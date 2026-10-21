"""
Widgets reutilizables de UmuLauncher (tarjetas de juego).
"""

import customtkinter as ctk

from core.config import (
    log, C_CARD, C_CARD_HOV, C_BORDER, C_PANEL, C_ACCENT, C_TEXT, C_DANGER,
    CARD_FRAME_W, CARD_H,
)
from core.covers import get_cover_image


# ==================== Tarjeta ====================
class GameCard(ctk.CTkFrame):
    def __init__(self, master, game, on_launch, on_edit, on_delete, on_select):
        super().__init__(master, fg_color=C_CARD, corner_radius=14,
                         border_width=1, border_color=C_BORDER,
                         width=CARD_FRAME_W, height=CARD_H + 60)
        self.grid_propagate(False)
        self.pack_propagate(False)
        self.game = game
        self.on_launch = on_launch
        self.on_edit = on_edit
        self.on_delete = on_delete
        self.on_select = on_select
        self.selected = False

        self.cover_label = ctk.CTkLabel(self, text="",
                                        image=get_cover_image(game))
        self.cover_label.pack(padx=8, pady=(8, 4))

        name = game.get("name", "Unknown")
        display = name if len(name) <= 26 else name[:24] + "…"
        self.name_label = ctk.CTkLabel(
            self, text=display,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=C_TEXT)
        self.name_label.pack(padx=6, pady=(0, 10))

        for w in (self, self.cover_label, self.name_label):
            w.bind("<Button-1>", self._on_click)
            w.bind("<Double-Button-1>", self._on_double)
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)

    def _on_click(self, e):
        if not self.selected:
            self.on_select(self.game)

    def _on_double(self, e):
        self.on_launch(self.game)

    def _on_enter(self, e):
        if not self.selected:
            self.configure(fg_color=C_CARD_HOV, border_color=C_ACCENT)

    def _on_leave(self, e):
        if not self.selected:
            self.configure(fg_color=C_CARD, border_color=C_BORDER)

    def set_selected(self, selected: bool):
        self.selected = selected
        if selected:
            self.configure(fg_color=C_CARD_HOV, border_color=C_ACCENT,
                           border_width=2)
        else:
            self.configure(fg_color=C_CARD, border_color=C_BORDER,
                           border_width=1)

    def _show_menu(self, x_root, y_root):
        try:
            self.on_select(self.game)
            app = self.winfo_toplevel()

            # Cerrar menú previo
            prev = getattr(app, "_open_menu_frame", None)
            if prev:
                try:
                    prev.destroy()
                except Exception:
                    log.exception("GameCard._show_menu: menú previo no se pudo cerrar")
                app._open_menu_frame = None

            # Tamaño provisional para que CTk no se queje
            MENU_W = 240
            MENU_H = 200

            menu = ctk.CTkFrame(
                app,
                width=MENU_W, height=MENU_H,
                fg_color=C_PANEL, corner_radius=10,
                border_width=1, border_color=C_BORDER,
            )

            def close():
                try:
                    menu.destroy()
                except Exception:
                    log.exception("GameCard._show_menu: no se pudo cerrar el menú")
                if getattr(app, "_open_menu_frame", None) is menu:
                    app._open_menu_frame = None

            def run(fn):
                close()
                app.after(20, fn)

            def item(text, cmd, color=C_TEXT):
                ctk.CTkButton(
                    menu, text=text, anchor="w",
                    fg_color="transparent", hover_color=C_CARD_HOV,
                    text_color=color, height=34, corner_radius=6,
                    font=ctk.CTkFont(size=12),
                    command=lambda: run(cmd),
                ).pack(fill="x", padx=4, pady=1)

            ctk.CTkFrame(menu, height=2, fg_color="transparent").pack()
            item("    ▶    Iniciar",
                 lambda: self.on_launch(self.game))
            item("    🛠    Iniciar (debug)",
                 lambda: self.on_launch(self.game, keep_open=True))
            ctk.CTkFrame(menu, height=1, fg_color=C_BORDER).pack(
                fill="x", padx=8, pady=4)
            item("    ✏    Editar / Propiedades",
                 lambda: self.on_edit(self.game))
            ctk.CTkFrame(menu, height=1, fg_color=C_BORDER).pack(
                fill="x", padx=8, pady=4)
            item("    🗑    Desinstalar",
                 lambda: self.on_delete(self.game), color=C_DANGER)
            ctk.CTkFrame(menu, height=2, fg_color="transparent").pack()

            # Fijar tamaño exacto en el constructor vía configure
            menu.update_idletasks()
            mw = max(MENU_W, menu.winfo_reqwidth())
            mh = menu.winfo_reqheight()
            menu.configure(width=mw, height=mh)

            # Coordenadas relativas a la app
            x = x_root - app.winfo_rootx()
            y = y_root - app.winfo_rooty()

            # Ajustar si se sale de la ventana
            if x + mw > app.winfo_width():
                x = max(4, app.winfo_width() - mw - 4)
            if y + mh > app.winfo_height():
                y = max(4, app.winfo_height() - mh - 4)
            if x < 4: x = 4
            if y < 4: y = 4

            # place() SIN width/height (CTk no lo permite)
            menu.place(x=x, y=y)
            menu.lift()
            app._open_menu_frame = menu

            menu.bind("<Escape>", lambda e: close())

        except Exception as e:
            print("[ERROR _show_menu]", repr(e), flush=True)
            import traceback
            traceback.print_exc()
