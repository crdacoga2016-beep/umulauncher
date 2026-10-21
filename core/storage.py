"""
Persistencia de UmuLauncher: escritura atómica y bloqueo de archivo (fcntl)
para settings y biblioteca de juegos.
"""

import fcntl, json, os, tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, Dict, List, Any

from core.config import (
    log, GAMES_FILE, SETTINGS_FILE, DEFAULT_SETTINGS,
)

# ==================== Storage (atómico + flock) ====================
def _lock_path(target: Path) -> Path:
    # Sidecar .lock: os.replace() cambia el inodo del archivo de datos,
    # por eso el bloqueo vive en un archivo aparte que nunca se reemplaza.
    return Path(str(target) + ".lock")


@contextmanager
def file_lock(target: Path, exclusive: bool = False):
    """LOCK_EX para escribir, LOCK_SH para leer."""
    with open(_lock_path(target), "a+", encoding="utf-8") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        try:
            yield
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)


def atomic_write_json(target: Path, data: Any) -> None:
    """Escribe en .tmp + os.replace() bajo LOCK_EX: sin corrupción ni carreras."""
    with file_lock(target, exclusive=True):
        fd, tmp = tempfile.mkstemp(dir=str(target.parent),
                                   prefix=target.name + ".", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, target)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise


def read_json_locked(target: Path) -> Optional[Any]:
    """Lee un JSON bajo LOCK_SH. Devuelve None si no existe."""
    if not target.exists():
        return None
    with file_lock(target, exclusive=False):
        with open(target, "r", encoding="utf-8") as f:
            return json.load(f)


# ==================== Settings ====================
def load_settings() -> Dict[str, Any]:
    try:
        data = read_json_locked(SETTINGS_FILE)
    except Exception:
        log.exception("load_settings: no se pudo leer %s", SETTINGS_FILE)
        data = None
    if not isinstance(data, dict):
        return dict(DEFAULT_SETTINGS)
    return {**DEFAULT_SETTINGS, **data}


def save_settings(s: Dict[str, Any]):
    atomic_write_json(SETTINGS_FILE, s)


# ==================== Games ====================
def load_games() -> List[Dict[str, Any]]:
    try:
        games = read_json_locked(GAMES_FILE)
    except Exception:
        log.exception("load_games: no se pudo leer %s", GAMES_FILE)
        return []
    if not isinstance(games, list):
        return []
    for g in games:
        if isinstance(g, dict) and not g.get("id"):
            g["id"] = os.urandom(8).hex()
    return games


def save_games(games: List[Dict[str, Any]]):
    atomic_write_json(GAMES_FILE, games)
