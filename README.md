# UmuLauncher

Launcher ligero y moderno para juegos de Windows en Linux, usando
[**umu-launcher**](https://github.com/Open-Wine-Components/umu-launcher) y
**Proton**. Interfaz oscura con biblioteca visual, carátulas automáticas y
menú contextual flotante.

Diseñado para CachyOS + Hyprland + Caelestia, pero funciona en cualquier
distro con Python 3.9+ y tkinter.

---

## Características

- Biblioteca visual con portadas (placeholder automático si no hay carátula)
- Configura Proton, Wine prefix, GAMEID y variables de entorno por juego
- **Importa tus scripts `.sh`** existentes de un solo clic
- Búsqueda de carátulas en Steam y SteamGridDB (opcional, con API key)
- Menú contextual estilo Lutris (clic derecho)
- Registro de tiempo de juego y última partida
- Se cierra solo al lanzar (opcional, configurable en Ajustes)
- `systemd-inhibit` opcional para evitar la suspensión mientras juegas

---

## Requisitos

- Linux con `umu-run` en el `PATH` (paquete `umu-launcher`)
- Python 3.9 o superior
- tkinter (viene con Python, o instálalo: `sudo pacman -S tk`)

---

## Instalación

```bash
git clone <URL_DEL_REPO>
cd umulauncher

python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

python umulaucher.py
```

La próxima vez solo:

```bash
cd umulauncher
source .venv/bin/activate
python umulaucher.py
```

### Instalación como paquete (opcional)

El proyecto incluye `pyproject.toml`, así que también puedes instalarlo:

```bash
pip install .
umulauncher
```

---

## Uso rápido

### Añadir un juego
Pulsa **+ Añadir** y rellena los campos. El ejecutable y el nombre son
obligatorios.

### Importar scripts `.sh` existentes
1. Pulsa **📄 Importar .sh**
2. Selecciona uno o varios archivos (multi-selección)
3. Se abre el editor ya rellenado con el nombre, `PROTONPATH`, `WINEPREFIX`,
   `GAMEID`/`STORE`, las variables `export`, el `cd` y el `.exe` de `umu-run`
4. Revisa, ponle carátula y pulsa **Guardar**

### Lanzar
- Clic izquierdo en la tarjeta → selecciona
- Doble clic / botón **▶ JUGAR** → lanza el juego
- Clic derecho → menú (Iniciar / Iniciar debug / Editar / Desinstalar)

---

## Variables de entorno por defecto

Los juegos **nuevos** se crean con dos variables verificadas con documentación
oficial:

| Variable        | Descripción                                             |
|-----------------|---------------------------------------------------------|
| `MANGOHUD=1`    | Overlay de [MangoHud](https://github.com/flightlessmango/MangoHud) |
| `UMU_GAMEMODE=1`| Activa GameMode dentro del Steam Linux Runtime          |

Las variables propias de umu (`GAMEID`, `STORE`, `PROTONPATH`, `WINEPREFIX`,
`UMU_LOG`, `PROTON_VERB`, …) las gestiona el propio launcher a través de la UI.

---

## Datos

- Configuración: `~/.config/umulauncher/`
  - `games.json` — biblioteca
  - `settings.json` — ajustes
- Portadas y logs: `~/.local/share/umulauncher/`
  - `covers/` — carátulas
  - `logs/` — logs de cada partida
  - `debug.log` — log interno de la aplicación

---

## Estructura del proyecto

```
umulauncher.py        # UI principal (UmuLauncherApp) y punto de entrada
core/
├── config.py         # rutas, logging, paleta y valores por defecto
├── storage.py        # persistencia atómica + bloqueo de archivo (fcntl)
├── covers.py         # descargas, Steam / SteamGridDB, placeholders
├── launcher.py       # comando umu-run, proceso hijo y watcher de tiempo
├── parser.py         # parseo de scripts .sh y formateadores
├── widgets.py        # GameCard
└── dialogs.py        # CoverPickerDialog, SettingsDialog, GameEditor
```

---

## Atajo de escritorio (opcional)

El archivo `umulaucher.desktop` está listo para usar con el comando
`umulauncher`. Tras instalarlo con `pip install .`, copia:

```bash
cp umulaucher.desktop ~/.local/share/applications/
```

---

## Licencia

[MIT](LICENSE)

Hecho con cariño ❤️
