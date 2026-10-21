"""
Configuración global de UmuLauncher: rutas, logging, paleta y valores por defecto.
"""

import logging
from pathlib import Path

# ==================== Paths ====================
APP_NAME = "umulauncher"
CONFIG_DIR = Path.home() / ".config" / APP_NAME
DATA_DIR = Path.home() / ".local" / "share" / APP_NAME
COVERS_DIR = DATA_DIR / "covers"
LOGS_DIR = DATA_DIR / "logs"
GAMES_FILE = CONFIG_DIR / "games.json"
SETTINGS_FILE = CONFIG_DIR / "settings.json"

for d in (CONFIG_DIR, DATA_DIR, COVERS_DIR, LOGS_DIR):
    d.mkdir(parents=True, exist_ok=True)

# ==================== Logging ====================
DEBUG_LOG = DATA_DIR / "debug.log"

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(DEBUG_LOG, encoding="utf-8")],
)
log = logging.getLogger("umulauncher")

# ==================== Paleta ====================
C_BG        = "#0f0e17"
C_PANEL     = "#1a1a2e"
C_CARD      = "#232334"
C_CARD_HOV  = "#2f2f47"
C_BORDER    = "#33334d"
C_ACCENT    = "#ffc107"
C_ACCENT_H  = "#ffb300"
C_TEXT      = "#fffffe"
C_MUTED     = "#a7a9be"
C_DANGER    = "#e94560"
C_DANGER_H  = "#ff5577"
C_OK        = "#4caf50"

# ==================== Defaults ====================
DEFAULT_PROTON_PATHS = [
    Path("/usr/share/steam/compatibilitytools.d"),
    Path.home() / ".local" / "share" / "Steam" / "compatibilitytools.d",
    Path.home() / ".steam" / "steam" / "compatibilitytools.d",
    Path.home() / ".steam" / "root" / "compatibilitytools.d",
]

# Variables de entorno por defecto para juegos nuevos.
# Solo variables verificadas con documentación oficial:
#   - MANGOHUD=1: habilita el overlay de MangoHud (man mangohud).
#   - UMU_GAMEMODE=1: activa GameMode dentro del runtime de umu (umu-launcher).
# El resto de variables de umu (GAMEID, STORE, PROTONPATH, WINEPREFIX,
# UMU_LOG, PROTON_VERB, ...) ya las gestiona el launcher y/o la propia UI.
DEFAULT_EXTRA_ENV = {
    "MANGOHUD": "1",
    "UMU_GAMEMODE": "1",
}

DEFAULT_SETTINGS = {
    "close_on_launch": True,
    "steamgriddb_api_key": "",
}

# ==================== Tamaños ====================
PLACEHOLDER_SIZE = (220, 330)
CARD_W, CARD_H = 220, 330

GRID_PAD = 6
CARD_FRAME_W = CARD_W + 14
CELL_W = CARD_FRAME_W + GRID_PAD * 2
