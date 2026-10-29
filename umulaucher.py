#!/usr/bin/env python3
"""
UmuLauncher — launcher ligero y moderno para umu-run.
Con menú contextual flotante estilo Lutris.
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageDraw, ImageTk
import os, sys, re, time, shutil
from pathlib import Path
from typing import Optional, Dict, List, Any

from core.config import (
    log, GAMES_FILE, COVERS_DIR,
    C_BG, C_PANEL, C_CARD, C_CARD_HOV, C_BORDER, C_ACCENT, C_ACCENT_H,
    C_TEXT, C_MUTED, C_DANGER,
    GRID_PAD, CELL_W,
)
from core.covers import get_cover_image
from core.storage import (
    load_settings, save_settings, load_games, save_games,
)
from core.launcher import launch_game, spawn_playtime_watcher
from core.parser import (
    parse_sh_script, format_playtime, format_last_played,
)
from core.widgets import GameCard
from core.dialogs import SettingsDialog, GameEditor

# ==================== App ====================
class UmuLauncherApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.title("UmuLauncher")
        self.geometry("1180x760")
        self.minsize(720, 560)
        self.configure(fg_color=C_BG)

        self._set_icon()

        self.settings = load_settings()
        self.games: List[Dict] = load_games()
        self.selected_game: Optional[Dict] = None
        self._cards: List[GameCard] = []
        self._current_cols = 0
        self._resize_job = None
        self._open_menu_frame = None
        self._launching: set = set()
        self._running: Dict[str, Any] = {}

        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self.refresh_library())

        self._build_ui()
        self._build_action_bar()
        self.refresh_library()

        # Atajos
        self.bind("<Control-n>", lambda e: self.add_game())
        self.bind("<Control-i>", lambda e: self.import_sh())
        self.bind("<Control-r>", lambda e: self.refresh_library())
        self.bind("<Control-comma>", lambda e: self.open_settings())
        self.bind("<F5>", lambda e: self.refresh_library())
        self.bind("<Escape>", lambda e: self._on_escape())
        self.bind("<Return>", lambda e: self._launch_selected())
        self.bind("<Delete>", lambda e: self._delete_selected())

        self.bind("<Configure>", self._on_resize)
        self.bind("<FocusIn>", self._on_focus_in)

        # Bind GLOBAL para click derecho
        self.bind_all("<Button-3>", self._on_right_click_global, add="+")
        self.bind_all("<Button-1>", self._on_global_click, add="+")

    def _on_right_click_global(self, event):
        widget = event.widget
        depth = 0
        while widget is not None and depth < 15:
            if isinstance(widget, GameCard):
                widget._show_menu(event.x_root, event.y_root)
                return
            widget = getattr(widget, "master", None)
            depth += 1

    def _on_global_click(self, event):
        menu = self._open_menu_frame
        if menu is None:
            return
        try:
            mx = menu.winfo_rootx()
            my = menu.winfo_rooty()
            mw = menu.winfo_width()
            mh = menu.winfo_height()
            inside = (mx <= event.x_root < mx + mw and
                      my <= event.y_root < my + mh)
            if not inside:
                menu.destroy()
                self._open_menu_frame = None
        except Exception:
            self._open_menu_frame = None

    def _on_resize(self, event):
        if event.widget is not self:
            return
        if self._resize_job:
            try:
                self.after_cancel(self._resize_job)
            except Exception:
                log.exception("_on_resize: after_cancel falló")
        self._resize_job = self.after(150, self._apply_resize)

    def _apply_resize(self):
        self._resize_job = None
        try:
            new_cols = self._compute_cols()
        except Exception:
            return
        if new_cols != self._current_cols:
            self.refresh_library()

    def _compute_cols(self) -> int:
        width = self.winfo_width()
        usable = width - 32
        cols = max(1, usable // CELL_W)
        return min(cols, 8)

    def _on_focus_in(self, event):
        if event.widget is not self:
            return
        try:
            fresh = load_games()
        except Exception:
            return
        changed = len(fresh) != len(self.games)
        if not changed:
            for a, b in zip(fresh, self.games):
                if (a.get("id") != b.get("id") or
                    a.get("last_played") != b.get("last_played") or
                    a.get("total_playtime") != b.get("total_playtime")):
                    changed = True
                    break
        if changed:
            self.games = fresh
            self.refresh_library()

    def _set_icon(self):
        try:
            size = 64
            img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            d.rounded_rectangle([2, 2, size - 3, size - 3], radius=14,
                                fill=(255, 193, 7, 255))
            d.rounded_rectangle([10, 10, size - 11, size - 11], radius=10,
                                fill=(30, 30, 40, 255))
            d.rectangle([28, 16, 36, 48], fill=(255, 193, 7, 255))
            d.polygon([(20, 18), (32, 8), (44, 18)], fill=(255, 193, 7, 255))
            photo = ImageTk.PhotoImage(img)
            self.iconphoto(True, photo)
            self._icon_ref = photo
        except Exception:
            log.exception("_set_icon: no se pudo generar el icono")

    def _build_ui(self):
        top = ctk.CTkFrame(self, height=64, corner_radius=0, fg_color=C_PANEL)
        top.pack(fill="x")
        top.pack_propagate(False)

        ctk.CTkLabel(top, text="⚔  UmuLauncher",
                     font=ctk.CTkFont(size=20, weight="bold"),
                     text_color=C_ACCENT).pack(side="left", padx=18)

        ctk.CTkButton(top, text="+  Añadir", width=110,
                      fg_color=C_ACCENT, hover_color=C_ACCENT_H,
                      text_color="#000000",
                      font=ctk.CTkFont(weight="bold"),
                      command=self.add_game).pack(side="right", padx=(6, 18), pady=14)
        ctk.CTkButton(top, text="📄  Importar .sh", width=140,
                      fg_color=C_CARD, hover_color=C_CARD_HOV,
                      text_color=C_TEXT,
                      command=self.import_sh).pack(side="right", padx=6, pady=14)
        ctk.CTkButton(top, text="⚙", width=42,
                      fg_color=C_CARD, hover_color=C_CARD_HOV,
                      text_color=C_ACCENT,
                      font=ctk.CTkFont(size=16, weight="bold"),
                      command=self.open_settings).pack(side="right", padx=6, pady=14)
        ctk.CTkButton(top, text="⟳", width=42,
                      fg_color=C_CARD, hover_color=C_CARD_HOV,
                      text_color=C_ACCENT,
                      font=ctk.CTkFont(size=16, weight="bold"),
                      command=self.refresh_library).pack(side="right", padx=6, pady=14)

        search_frame = ctk.CTkFrame(top, fg_color=C_CARD, corner_radius=10,
                                    border_width=1, border_color=C_BORDER,
                                    height=38, width=320)
        search_frame.pack(side="left", padx=(20, 0), pady=13)
        search_frame.pack_propagate(False)
        ctk.CTkLabel(search_frame, text="🔍", text_color=C_MUTED,
                     font=ctk.CTkFont(size=14)).pack(side="left", padx=(10, 4))
        ctk.CTkEntry(search_frame, textvariable=self._search_var,
                     placeholder_text="Buscar juegos…",
                     fg_color="transparent", border_width=0,
                     text_color=C_TEXT, width=280).pack(side="left", padx=(0, 10))

        self.library = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
            scrollbar_button_color=C_PANEL,
            scrollbar_button_hover_color=C_CARD_HOV)
        self.library.pack(fill="both", expand=True, padx=16, pady=12)

        self.status = ctk.CTkLabel(self, text="", text_color=C_MUTED,
                                   font=ctk.CTkFont(size=11), anchor="w")
        self.status.pack(fill="x", padx=20, pady=(0, 8))

        if not shutil.which("umu-run"):
            warn = ctk.CTkFrame(self, fg_color="#3a1a1a", corner_radius=8,
                                border_width=1, border_color=C_DANGER)
            warn.pack(fill="x", padx=16, pady=(0, 10))
            ctk.CTkLabel(
                warn,
                text="⚠  umu-run no está en el PATH. Instálalo para poder lanzar juegos.",
                text_color=C_DANGER, font=ctk.CTkFont(weight="bold")
            ).pack(padx=14, pady=8, anchor="w")

    def _build_action_bar(self):
        self.action_bar = ctk.CTkFrame(self, corner_radius=0, fg_color=C_PANEL,
                                       border_width=1, border_color=C_BORDER)

        inner = ctk.CTkFrame(self.action_bar, fg_color="transparent")
        inner.pack(fill="x", padx=18, pady=12)

        self.ab_cover = ctk.CTkLabel(inner, text="", width=60, height=90)
        self.ab_cover.pack(side="left", padx=(0, 14))

        info = ctk.CTkFrame(inner, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True)
        self.ab_name = ctk.CTkLabel(info, text="",
                                    font=ctk.CTkFont(size=16, weight="bold"),
                                    text_color=C_TEXT, anchor="w")
        self.ab_name.pack(anchor="w")
        self.ab_path = ctk.CTkLabel(info, text="", font=ctk.CTkFont(size=11),
                                    text_color=C_MUTED, anchor="w")
        self.ab_path.pack(anchor="w", pady=(4, 0))
        self.ab_stats = ctk.CTkLabel(info, text="", font=ctk.CTkFont(size=11),
                                     text_color=C_MUTED, anchor="w")
        self.ab_stats.pack(anchor="w", pady=(2, 0))

        btns = ctk.CTkFrame(inner, fg_color="transparent")
        btns.pack(side="right")
        ctk.CTkButton(btns, text="▶   JUGAR", width=150, height=46,
                      fg_color=C_ACCENT, hover_color=C_ACCENT_H,
                      text_color="#000000",
                      font=ctk.CTkFont(size=14, weight="bold"),
                      command=self._launch_selected).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="✏", width=46, height=46,
                      fg_color=C_CARD, hover_color=C_CARD_HOV,
                      text_color=C_ACCENT, font=ctk.CTkFont(size=16),
                      command=self._edit_selected).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="🗑", width=46, height=46,
                      fg_color=C_CARD, hover_color="#7a1a2b",
                      text_color=C_DANGER, font=ctk.CTkFont(size=16),
                      command=self._delete_selected).pack(side="left", padx=4)

        self._ab_img_ref = None

    def _select_game(self, game: Dict):
        self.selected_game = game
        for card in self._cards:
            card.set_selected(card.game.get("id") == game.get("id"))
        self._show_action_bar(game)

    def _clear_selection(self):
        self.selected_game = None
        for card in self._cards:
            card.set_selected(False)
        self._hide_action_bar()

    def _show_action_bar(self, game: Dict):
        self.ab_name.configure(text=game.get("name", "(sin nombre)"))
        exe = game.get("exe", "") or ""
        if len(exe) > 90:
            exe = "…" + exe[-87:]
        self.ab_path.configure(text=exe or "(sin ejecutable)")

        last = game.get("last_played", 0)
        total = game.get("total_playtime", 0)
        parts = []
        parts.append(f"🕐 Última vez: {format_last_played(last)}")
        if total:
            parts.append(f"🎮 Tiempo: {format_playtime(total)}")
        self.ab_stats.configure(text="   ·   ".join(parts))

        img = get_cover_image(game, size=(60, 90))
        self._ab_img_ref = img
        self.ab_cover.configure(image=img)

        if not self.action_bar.winfo_ismapped():
            self.action_bar.pack(fill="x", before=self.status)

    def _hide_action_bar(self):
        self.action_bar.pack_forget()

    def _on_escape(self):
        if self._open_menu_frame:
            try:
                self._open_menu_frame.destroy()
            except Exception:
                log.exception("_on_escape: no se pudo cerrar el menú contextual")
            self._open_menu_frame = None
            return
        if self.selected_game:
            self._clear_selection()
        else:
            self.quit_app()

    def _launch_selected(self):
        if self.selected_game:
            self.launch(self.selected_game)

    def _edit_selected(self):
        if self.selected_game:
            self.edit_game(self.selected_game)

    def _delete_selected(self):
        if self.selected_game:
            self.delete_game(self.selected_game)

    def refresh_library(self):
        for w in self.library.winfo_children():
            w.destroy()
        self._cards = []

        query = self._search_var.get().strip().lower()
        filtered = [g for g in self.games
                    if query in g.get("name", "").lower()] if query else list(self.games)
        filtered.sort(key=lambda g: g.get("last_played", 0) or 0, reverse=True)

        if not filtered:
            msg = (f"No se encontraron juegos para “{query}”" if query else
                   "Aún no tienes juegos.\n\n"
                   "• Haz clic en “+ Añadir” para crear uno\n"
                   "• O en “Importar .sh” para cargar tus scripts existentes")
            ctk.CTkLabel(self.library, text=msg, font=ctk.CTkFont(size=15),
                         text_color=C_MUTED, justify="center").pack(expand=True, pady=100)
            self.status.configure(text="0 juegos" + (f" (filtro: '{query}')" if query else ""))
            self._clear_selection()
            self._current_cols = 0
            return

        cols = self._compute_cols()
        self._current_cols = cols

        for i, game in enumerate(filtered):
            card = GameCard(
                self.library, game=game,
                on_launch=self.launch,
                on_edit=self.edit_game,
                on_delete=self.delete_game,
                on_select=self._select_game,
            )
            card.grid(row=i // cols, column=i % cols,
                      padx=GRID_PAD, pady=GRID_PAD, sticky="n")
            self._cards.append(card)

        if self.selected_game:
            still_there = next(
                (g for g in self.games if g.get("id") == self.selected_game.get("id")),
                None)
            if still_there:
                self.selected_game = still_there
                for card in self._cards:
                    card.set_selected(card.game.get("id") == still_there.get("id"))
                self._show_action_bar(still_there)
            else:
                self._clear_selection()

        total, shown = len(self.games), len(filtered)
        text = f"{total} juego{'s' if total != 1 else ''}"
        if query:
            text += f" — mostrando {shown}"
        self.status.configure(text=text)

    def open_settings(self):
        def on_save(new_settings):
            self.settings = new_settings
            save_settings(self.settings)
            self.status.configure(text="⚙ Ajustes guardados")
        SettingsDialog(self, self.settings, on_save)

    def add_game(self):
        def on_save(data):
            self.games.append(data)
            save_games(self.games)
            self.refresh_library()
            self.status.configure(text=f"✅ «{data['name']}» añadido")
        GameEditor(self, on_save=on_save)

    def import_sh(self):
        paths = filedialog.askopenfilenames(
            parent=self, title="Seleccionar scripts .sh",
            filetypes=[("Scripts de shell", "*.sh"), ("Todos", "*.*")])
        if not paths:
            return
        count = 0
        for path in paths:
            try:
                data = parse_sh_script(path)

                def make_saver(parsed):
                    def on_save(final):
                        self.games.append(final)
                        save_games(self.games)
                        self.refresh_library()
                    return on_save

                GameEditor(self, game=data, on_save=make_saver(data))
                count += 1
            except Exception as e:
                messagebox.showerror("Error de importación",
                                     f"No se pudo leer {Path(path).name}:\n{e}",
                                     parent=self)
        if count:
            self.status.configure(
                text=f"Importados {count} script(s) — revisa y guarda en cada ventana")

    def edit_game(self, game):
        def on_save(data):
            gid = game.get("id")
            for i, g in enumerate(self.games):
                if (gid and g.get("id") == gid) or \
                   (not gid and g.get("exe") == game.get("exe")):
                    self.games[i] = data
                    break
            else:
                self.games.append(data)
            save_games(self.games)
            self.refresh_library()
            self.status.configure(text=f"💾 «{data['name']}» actualizado")
        GameEditor(self, game=game, on_save=on_save)

    def delete_game(self, game):
        if not game:
            return
        if not messagebox.askyesno(
            "Desinstalar",
            f"¿Eliminar «{game.get('name')}» de tu biblioteca?\n\n"
            "Esto NO borra los archivos del juego, solo la entrada.",
            parent=self):
            return

        gid = game.get("id")
        exe = game.get("exe")
        self.games = [
            g for g in self.games
            if not ((gid and g.get("id") == gid)
                    or (not gid and g.get("exe") == exe))
        ]
        save_games(self.games)

        if self.selected_game and self.selected_game.get("id") == gid:
            self.selected_game = None

        cover = game.get("cover")
        try:
            if cover and Path(cover).exists() and str(COVERS_DIR) in str(cover):
                Path(cover).unlink()
        except Exception:
            log.exception("delete_game: no se pudo borrar la carátula %s", cover)

        self.refresh_library()
        self.status.configure(text=f"🗑 «{game.get('name')}» eliminado")

    def _game_key(self, game) -> str:
        return str(game.get("id") or game.get("exe") or game.get("name") or "")

    def launch(self, game, keep_open: bool = False):
        key = self._game_key(game)

        if key in self._running:
            self.status.configure(
                text=f"⏳ «{game.get('name')}» ya está en ejecución")
            return

        if key in self._launching:
            self.status.configure(
                text=f"⏳ «{game.get('name')}» se está iniciando…")
            return

        self._launching.add(key)
        self.status.configure(text=f"🚀 Iniciando {game.get('name')}…")
        self.update_idletasks()

        started_at = time.time()

        close_cb = None
        if not keep_open and self.settings.get("close_on_launch", True):
            close_cb = self.quit_app

        try:
            result = launch_game(game)
        except Exception:
            log.exception("launch: error inesperado al iniciar %s", game.get("name"))
            result = None

        if not result:
            self._launching.discard(key)
            self.status.configure(text="❌ Fallo al iniciar — revisa el log")
            return

        proc, log_file = result
        # Comprobación diferida: sin time.sleep en el hilo de la UI.
        self.after(1200, self._finish_launch,
                   game, proc, log_file, started_at, keep_open, close_cb)

    def _finish_launch(self, game, proc, log_file, started_at,
                       keep_open, close_cb):
        key = self._game_key(game)
        self._launching.discard(key)

        if proc.poll() is not None:
            try:
                content = log_file.read_text(encoding="utf-8", errors="replace")
            except Exception:
                log.exception("_finish_launch: no se pudo leer %s", log_file)
                content = "(no se pudo leer el log)"
            self.status.configure(text="❌ Fallo al iniciar — revisa el log")
            messagebox.showerror(
                "Fallo al iniciar",
                f"El proceso terminó con código {proc.returncode}.\n\n"
                f"Log: {log_file}\n\n{content[-1500:]}",
                parent=self)
            return

        # Éxito: solo ahora se registra el playtime (last_played).
        for g in self.games:
            if g.get("id") == game.get("id"):
                g["last_played"] = int(started_at)
                break
        save_games(self.games)
        spawn_playtime_watcher(GAMES_FILE, proc.pid, game.get("id", ""),
                               started_at)

        self._running[key] = proc
        self._poll_running(key, proc)

        if keep_open:
            self.status.configure(text="🔧 Modo debug activo (launcher sigue abierto)")
            messagebox.showinfo(
                "Lanzado (modo debug)",
                f"Proceso corriendo (PID {proc.pid}).\n\nLog:\n{log_file}",
                parent=self)
        elif close_cb:
            close_cb()
        else:
            self.status.configure(text="🎮 Juego en ejecución — launcher sigue abierto")

    def _poll_running(self, key: str, proc):
        if proc.poll() is None:
            self.after(2000, self._poll_running, key, proc)
        else:
            self._running.pop(key, None)

    def quit_app(self):
        try:
            self.destroy()
        finally:
            sys.exit(0)


# ==================== Entry ====================
def main():
    if not shutil.which("umu-run"):
        print("⚠  umu-run no está en el PATH. Instálalo para poder lanzar juegos.")
    app = UmuLauncherApp()
    app.mainloop()


if __name__ == "__main__":
    main()
