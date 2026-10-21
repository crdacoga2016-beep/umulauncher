"""
Diálogos de UmuLauncher: selector de carátulas, ajustes y editor de juegos.
"""

import io, os, shutil, threading
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Optional, Dict, List

import customtkinter as ctk
import tkinter as tk
from PIL import Image

from core.config import (
    log, COVERS_DIR, DEFAULT_EXTRA_ENV,
    C_BG, C_PANEL, C_CARD, C_CARD_HOV, C_BORDER, C_ACCENT, C_ACCENT_H,
    C_TEXT, C_MUTED,
)
from core.covers import (
    get_cover_image, steam_search, fetch_steam_cover, fetch_sgdb_cover,
    _download_bytes, invalidate_cover_cache,
)
from core.parser import find_protons


# ==================== Base modal ====================
class _ModalDialog(ctk.CTkToplevel):
    def __init__(self, master, title: str, geometry: str, header_text: str,
                 header_height: int = 54, header_font_size: int = 15,
                 header_padx: int = 16):
        super().__init__(master)
        self.title(title)
        self.geometry(geometry)
        self.configure(fg_color=C_BG)
        self.transient(master)

        header = ctk.CTkFrame(self, fg_color=C_PANEL, height=header_height,
                              corner_radius=0)
        header.pack(fill="x")
        header.pack_propagate(False)
        ctk.CTkLabel(header, text=header_text,
                     font=ctk.CTkFont(size=header_font_size, weight="bold"),
                     text_color=C_ACCENT).pack(side="left", padx=header_padx)

    def _activate(self):
        try:
            self.lift(); self.focus_force(); self.grab_set()
        except Exception:
            log.exception("%s: no se pudo activar el modal",
                          type(self).__name__)

    def _primary_button(self, parent, text, command, width=130,
                        height=None, **kwargs):
        opts = dict(
            text=text, width=width,
            fg_color=C_ACCENT, hover_color=C_ACCENT_H,
            text_color="#000000",
            font=ctk.CTkFont(weight="bold"),
            command=command)
        if height is not None:
            opts["height"] = height
        opts.update(kwargs)
        return ctk.CTkButton(parent, **opts)

    def _check_box(self, parent, text, variable, **kwargs):
        return ctk.CTkCheckBox(
            parent, text=text, variable=variable,
            fg_color=C_ACCENT, hover_color=C_ACCENT_H,
            text_color=C_TEXT, checkmark_color="#000000", **kwargs)

    def _add_footer(self, save_cmd, cancel_width=110, save_width=130,
                    padx=16, pady=14, button_height=36):
        footer = ctk.CTkFrame(self, fg_color=C_PANEL, height=64,
                              corner_radius=0)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)

        cancel_opts = dict(
            text="Cancelar", width=cancel_width,
            fg_color=C_CARD, hover_color=C_CARD_HOV,
            text_color=C_TEXT, command=self.destroy)
        if button_height is not None:
            cancel_opts["height"] = button_height
        ctk.CTkButton(footer, **cancel_opts).pack(
            side="left", padx=padx, pady=pady)

        self._primary_button(footer, "💾  Guardar", save_cmd,
                             width=save_width,
                             height=button_height).pack(
            side="right", padx=padx, pady=pady)

    def _run_bg(self, fn, on_done=None):
        self.configure(cursor="watch")
        self.update_idletasks()

        def worker():
            try:
                result = fn()
            except Exception:
                log.exception("_run_bg: fallo en la tarea en segundo plano")
                result = None

            def finish():
                self.configure(cursor="")
                if on_done is not None:
                    on_done(result)

            self.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()


# ==================== Cover Picker ====================
class CoverPickerDialog(_ModalDialog):
    def __init__(self, master, query: str, results: List[Dict], on_pick):
        super().__init__(master,
                         title=f"Resultados para «{query}»",
                         geometry="640x520",
                         header_text="🎨  Elige la carátula correcta")
        self.on_pick = on_pick
        self.results = results
        self._thumbs: List = []

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=12, pady=12)

        if not results:
            ctk.CTkLabel(scroll, text="Sin resultados.",
                         text_color=C_MUTED).pack(pady=40)
            return

        for r in results:
            self._add_row(scroll, r)

        self.after(80, self._activate)

    def _add_row(self, parent, item):
        row = ctk.CTkFrame(parent, fg_color=C_CARD, corner_radius=10,
                           border_width=1, border_color=C_BORDER)
        row.pack(fill="x", pady=6, padx=4)

        thumb_lbl = ctk.CTkLabel(row, text="", width=140, height=60)
        thumb_lbl.pack(side="left", padx=10, pady=8)

        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True, padx=(0, 10))
        ctk.CTkLabel(info, text=item.get("name", ""),
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=C_TEXT, anchor="w",
                     wraplength=320, justify="left").pack(anchor="w", pady=(8, 2))
        ctk.CTkLabel(info, text=f"AppID: {item.get('id', '?')}",
                     font=ctk.CTkFont(size=11),
                     text_color=C_MUTED, anchor="w").pack(anchor="w")

        self._primary_button(row, "Usar", lambda: self._pick(item),
                             width=80).pack(side="right", padx=10)

        url = item.get("tiny_image", "")
        if url:
            threading.Thread(target=self._load_thumb,
                             args=(url, thumb_lbl), daemon=True).start()

    def _load_thumb(self, url, label):
        data = _download_bytes(url, timeout=8)
        if not data:
            return
        try:
            img = Image.open(io.BytesIO(data)).convert("RGB")
            img = img.resize((140, 60), Image.Resampling.LANCZOS)
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(140, 60))
            self.after(0, lambda: self._set_thumb(label, ctk_img))
        except Exception:
            log.exception("_load_thumb: no se pudo cargar la miniatura %s", url)

    def _set_thumb(self, label, img):
        try:
            label.configure(image=img)
            self._thumbs.append(img)
        except Exception:
            log.exception("_set_thumb: no se pudo asignar la miniatura")

    def _pick(self, item):
        self.on_pick(item)
        self.destroy()


# ==================== Ajustes ====================
class SettingsDialog(_ModalDialog):
    def __init__(self, master, settings: Dict, on_save):
        super().__init__(master, title="Ajustes", geometry="560x440",
                         header_text="⚙  Ajustes")
        self.settings = dict(settings)
        self.on_save = on_save
        self.resizable(False, False)

        self._add_footer(self._save)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=16)

        ctk.CTkLabel(body, text="Comportamiento",
                     font=ctk.CTkFont(weight="bold"),
                     text_color=C_TEXT).pack(anchor="w", pady=(0, 8))

        self.close_var = tk.BooleanVar(value=bool(settings.get("close_on_launch", True)))
        self._check_box(
            body, "Cerrar el launcher al iniciar un juego", self.close_var
        ).pack(anchor="w", pady=4)

        ctk.CTkLabel(body,
                     text="Si está desactivado, la ventana permanece abierta "
                          "mientras juegas (útil para cambiar de juego rápido).",
                     text_color=C_MUTED, font=ctk.CTkFont(size=11),
                     wraplength=490, justify="left").pack(anchor="w", pady=(0, 16))

        ctk.CTkFrame(body, height=1, fg_color=C_BORDER).pack(fill="x", pady=8)

        ctk.CTkLabel(body, text="Carátulas automáticas — SteamGridDB (opcional)",
                     font=ctk.CTkFont(weight="bold"),
                     text_color=C_TEXT).pack(anchor="w", pady=(8, 4))
        ctk.CTkLabel(body,
                     text="Obtén una key gratis en steamgriddb.com → Preferences → API.\n"
                          "Sin key solo se usa la búsqueda pública de Steam.",
                     text_color=C_MUTED, font=ctk.CTkFont(size=11),
                     wraplength=490, justify="left").pack(anchor="w", pady=(0, 6))

        self.sgdb_entry = ctk.CTkEntry(
            body, placeholder_text="Pega tu API key aquí…",
            fg_color=C_CARD, border_color=C_BORDER,
            text_color=C_TEXT, height=34)
        self.sgdb_entry.pack(fill="x")
        self.sgdb_entry.insert(0, settings.get("steamgriddb_api_key", ""))

        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<Return>", lambda e: self._save())
        self.after(80, self._activate)

    def _save(self):
        self.settings["close_on_launch"] = bool(self.close_var.get())
        self.settings["steamgriddb_api_key"] = self.sgdb_entry.get().strip()
        if self.on_save:
            self.on_save(self.settings)
        self.destroy()


# ==================== Editor ====================
class GameEditor(_ModalDialog):
    def __init__(self, master, game: Optional[Dict] = None, on_save=None):
        is_new = not bool(game and game.get("name"))
        super().__init__(
            master,
            title="Añadir juego" if is_new else f"Editar — {game.get('name', '')}",
            geometry="760x720",
            header_text=("➕  Añadir juego" if is_new else "✏️  Propiedades"),
            header_height=60, header_font_size=16, header_padx=18)
        self.game = dict(game) if game else {}
        self.on_save = on_save
        self.entries = {}

        self.minsize(680, 600)

        self.tabview = ctk.CTkTabview(
            self, fg_color=C_BG,
            segmented_button_fg_color=C_PANEL,
            segmented_button_selected_color=C_ACCENT,
            segmented_button_selected_hover_color=C_ACCENT_H,
            segmented_button_unselected_color=C_PANEL,
            text_color=C_TEXT)
        self.tabview.pack(fill="both", expand=True, padx=14, pady=(14, 6))

        self.tab_general = self.tabview.add("General")
        self.tab_options = self.tabview.add("Opciones")
        self.tab_proton  = self.tabview.add("Proton / Sistema")
        self.tab_env     = self.tabview.add("Entorno")

        self._build_general()
        self._build_options()
        self._build_proton()
        self._build_env()

        self._add_footer(self.save, cancel_width=120, save_width=140,
                         padx=18, pady=12, button_height=None)

        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<Control-Return>", lambda e: self.save())
        self.after(80, self._activate)

    def _add_field(self, parent, label, key, default="", placeholder="", browse=None):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", pady=5)
        ctk.CTkLabel(frame, text=label, width=150, anchor="w",
                     text_color=C_MUTED).pack(side="left")
        entry = ctk.CTkEntry(
            frame, placeholder_text=placeholder, height=32,
            fg_color=C_CARD, border_color=C_BORDER, text_color=C_TEXT)
        entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        if browse:
            ctk.CTkButton(frame, text="…", width=38, height=32,
                          fg_color=C_PANEL, hover_color=C_CARD_HOV,
                          text_color=C_ACCENT,
                          command=lambda: browse(entry)).pack(side="right")
        val = self.game.get(key, default) or ""
        entry.insert(0, str(val))
        self.entries[key] = entry
        return entry

    def _build_general(self):
        body = ctk.CTkFrame(self.tab_general, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=6, pady=8)

        left = ctk.CTkFrame(body, fg_color="transparent")
        left.pack(side="left", fill="y", padx=(0, 18))

        ctk.CTkLabel(left, text="Carátula",
                     font=ctk.CTkFont(weight="bold"),
                     text_color=C_TEXT).pack(anchor="w", pady=(0, 6))

        self.cover_preview_btn = ctk.CTkButton(
            left, text="", width=160, height=240,
            fg_color=C_CARD, hover_color=C_CARD_HOV,
            image=get_cover_image(self.game, size=(160, 240)),
            command=self._browse_cover)
        self.cover_preview_btn.pack()

        ctk.CTkButton(
            left, text="🔍  Buscar en internet",
            width=160, height=30,
            fg_color=C_PANEL, hover_color=C_CARD_HOV,
            text_color=C_ACCENT,
            command=self._auto_fetch_cover
        ).pack(pady=(10, 4))

        ctk.CTkLabel(left, text="Clic en la imagen para archivo local",
                     text_color=C_MUTED, font=ctk.CTkFont(size=10),
                     wraplength=160, justify="center").pack()

        right = ctk.CTkFrame(body, fg_color="transparent")
        right.pack(side="right", fill="both", expand=True)

        self._add_field(right, "Nombre *", "name", placeholder="Ej: Hollow Knight")
        self._add_field(right, "Ejecutable *", "exe",
                        placeholder="/ruta/juego.exe", browse=self._browse_exe)
        self._add_field(right, "Directorio", "workdir",
                        placeholder="/ruta/directorio", browse=self._browse_dir)

        self.cover_var = tk.StringVar(value=self.game.get("cover", "") or "")

    def _build_options(self):
        f = self.tab_options
        self._add_field(f, "Argumentos", "args", placeholder="-windowed -novid")
        self._add_field(f, "Wine Prefix", "prefix",
                        default=str(Path.home() / ".local/share/wineprefixes/DEFAULT"),
                        browse=self._browse_dir)
        self._add_field(f, "Store", "store", default="steam",
                        placeholder="steam / egs / gog / ubisoft")
        self._add_field(f, "Steam AppID", "gameid",
                        placeholder="Opcional — se autocompleta al buscar carátula")

    def _build_proton(self):
        f = self.tab_proton
        p_frame = ctk.CTkFrame(f, fg_color="transparent")
        p_frame.pack(fill="x", pady=8)
        ctk.CTkLabel(p_frame, text="Versión de Proton", width=150,
                     anchor="w", text_color=C_MUTED).pack(side="left")

        protons = find_protons()
        current = self.game.get("proton", "")
        if current and current not in protons:
            protons = [current] + protons
        values = protons or ["(ninguno encontrado)"]
        self.proton_var = ctk.StringVar(value=current or values[0])
        ctk.CTkOptionMenu(
            p_frame, variable=self.proton_var, values=values,
            fg_color=C_CARD, button_color=C_PANEL,
            button_hover_color=C_ACCENT_H, text_color=C_TEXT,
            dropdown_fg_color=C_PANEL, dropdown_text_color=C_TEXT,
            dropdown_hover_color=C_ACCENT
        ).pack(side="left", fill="x", expand=True)

        ctk.CTkFrame(f, height=1, fg_color=C_BORDER).pack(fill="x", pady=12)

        self.inhibit_var = tk.BooleanVar(value=self.game.get("inhibit", True))
        self._check_box(
            f, "Usar systemd-inhibit (evita suspensión de energía al jugar)",
            self.inhibit_var
        ).pack(anchor="w", pady=6)

    def _build_env(self):
        f = self.tab_env
        ctk.CTkLabel(f, text="Variables de entorno (KEY=VALUE, una por línea):",
                     anchor="w", text_color=C_MUTED).pack(fill="x", pady=(4, 6))

        default_extra = self.game.get("extra_env", "")
        if isinstance(default_extra, dict):
            default_extra = "\n".join(f"{k}={v}" for k, v in default_extra.items())
        if not default_extra:
            default_extra = "\n".join(f"{k}={v}" for k, v in DEFAULT_EXTRA_ENV.items())

        self.extra_text = ctk.CTkTextbox(
            f, height=280, fg_color=C_CARD, text_color=C_TEXT,
            border_color=C_BORDER, border_width=1)
        self.extra_text.pack(fill="both", expand=True)
        self.extra_text.insert("1.0", default_extra)

    def _browse_exe(self, entry):
        path = filedialog.askopenfilename(
            parent=self, title="Seleccionar ejecutable",
            filetypes=[("Ejecutables", "*.exe *.EXE *.bat *.sh"), ("Todos", "*.*")])
        if path:
            entry.delete(0, "end")
            entry.insert(0, path)
            if not self.entries["workdir"].get().strip():
                self.entries["workdir"].delete(0, "end")
                self.entries["workdir"].insert(0, str(Path(path).parent))

    def _browse_dir(self, entry):
        path = filedialog.askdirectory(parent=self, title="Seleccionar directorio")
        if path:
            entry.delete(0, "end")
            entry.insert(0, path)

    def _browse_cover(self):
        path = filedialog.askopenfilename(
            parent=self, title="Seleccionar carátula",
            filetypes=[("Imágenes", "*.png *.jpg *.jpeg *.webp *.bmp"), ("Todos", "*.*")])
        if not path:
            return
        try:
            dest = COVERS_DIR / f"{Path(path).stem}_{os.urandom(4).hex()}{Path(path).suffix}"
            shutil.copy2(path, dest)
            self._apply_cover(str(dest))
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo copiar la carátula:\n{e}",
                                 parent=self)

    def _apply_cover(self, path: str):
        self.cover_var.set(path)
        invalidate_cover_cache()
        new_img = get_cover_image(
            {"cover": path, "name": self.game.get("name", "")}, size=(160, 240))
        self.cover_preview_btn.configure(image=new_img)

    def _auto_fetch_cover(self):
        name = self.entries["name"].get().strip()
        if not name:
            messagebox.showwarning("Falta el nombre",
                                   "Escribe primero el nombre del juego.",
                                   parent=self)
            return
        api_key = getattr(self.master, "settings", {}).get(
            "steamgriddb_api_key", "")
        self._run_bg(
            lambda: steam_search(name),
            lambda results: self._on_cover_results(name, api_key,
                                                   results or []))

    def _on_cover_results(self, name, api_key, results):
        if results:
            CoverPickerDialog(
                self, name, results,
                lambda item: self._on_cover_picked(name, item))
            return
        if api_key:
            self._run_bg(
                lambda: fetch_sgdb_cover(name, api_key),
                lambda cover: self._on_cover_downloaded(name, cover))
            return
        messagebox.showinfo(
            "Sin resultados",
            f"No encontré «{name}» en Steam.\n\n"
            "• Prueba con el nombre exacto del juego.\n"
            "• O configura una key de SteamGridDB en Ajustes.",
            parent=self)

    def _on_cover_picked(self, name, item):
        appid = item["id"]
        self._run_bg(
            lambda: fetch_steam_cover(appid),
            lambda cover: self._on_cover_downloaded(name, cover, appid))

    def _on_cover_downloaded(self, name, cover, appid=None):
        if cover:
            self._apply_cover(str(cover))
            if appid and "gameid" in self.entries:
                self.entries["gameid"].delete(0, "end")
                self.entries["gameid"].insert(0, appid)
            return
        if appid is not None:
            messagebox.showwarning(
                "Sin carátula",
                "Steam no tiene carátula vertical para ese AppID.",
                parent=self)
            return
        messagebox.showinfo(
            "Sin resultados",
            f"No encontré carátula para «{name}».",
            parent=self)

    def save(self):
        name = self.entries["name"].get().strip()
        exe = self.entries["exe"].get().strip()
        if not name or not exe:
            messagebox.showwarning("Campos incompletos",
                                   "El nombre y el ejecutable son obligatorios.",
                                   parent=self)
            return

        data = {
            "name": name,
            "exe": exe,
            "workdir": self.entries["workdir"].get().strip() or None,
            "args": self.entries["args"].get().strip(),
            "proton": self.proton_var.get() if self.proton_var.get() != "(ninguno encontrado)" else "",
            "prefix": self.entries["prefix"].get().strip(),
            "gameid": self.entries["gameid"].get().strip(),
            "store": self.entries["store"].get().strip() or "steam",
            "cover": self.cover_var.get().strip(),
            "extra_env": self.extra_text.get("1.0", "end").strip(),
            "inhibit": self.inhibit_var.get(),
            "id": self.game.get("id") or os.urandom(8).hex(),
            "last_played": self.game.get("last_played", 0),
            "total_playtime": self.game.get("total_playtime", 0),
        }

        invalidate_cover_cache(name=data["name"], cover=data["cover"] or None)

        if self.on_save:
            self.on_save(data)
        self.destroy()
