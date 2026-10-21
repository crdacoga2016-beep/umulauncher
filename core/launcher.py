"""
Lógica de lanzamiento de UmuLauncher: construcción del comando umu-run,
proceso hijo y watcher de tiempo de juego.
"""

import os, re, shlex, shutil, subprocess, sys, time
from pathlib import Path
from tkinter import messagebox
from typing import Optional, Dict, Any, Tuple

from core.config import log, LOGS_DIR, DEBUG_LOG

# ==================== Watcher ====================
_WATCHER_CODE = r"""
import fcntl, json, logging, os, sys, time
pid        = int(sys.argv[1])
game_id    = sys.argv[2]
started_at = float(sys.argv[3])
games_file = sys.argv[4]
debug_log  = sys.argv[5]

logging.basicConfig(level=logging.DEBUG, filename=debug_log, filemode="a",
                    format="%(asctime)s %(levelname)s [watcher] %(message)s")

lock_file = games_file + ".lock"
tmp_file  = games_file + ".tmp"

while True:
    try:
        os.kill(pid, 0)
    except OSError:
        break
    time.sleep(10)
    if time.time() - started_at > 24 * 3600:
        break

elapsed = int(time.time() - started_at)
try:
    with open(lock_file, "a+") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)   # le-modifica-escribe: LOCK_EX
        try:
            with open(games_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            for g in data:
                if g.get("id") == game_id:
                    g["total_playtime"] = int(g.get("total_playtime", 0)) + elapsed
                    g["last_played"] = int(started_at)
                    break
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_file, games_file)   # reemplazo atómico
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)
except Exception:
    logging.exception("watcher: no se pudo actualizar el playtime de %s", game_id)
    try:
        os.unlink(tmp_file)
    except OSError:
        pass
"""


def spawn_playtime_watcher(games_file: Path, pid: int, game_id: str,
                           started_at: float):
    try:
        subprocess.Popen(
            [sys.executable, "-c", _WATCHER_CODE,
             str(pid), str(game_id), str(started_at), str(games_file),
             str(DEBUG_LOG)],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )
    except Exception:
        log.exception("spawn_playtime_watcher: no se pudo lanzar el watcher (pid=%s)", pid)


# ==================== Launch ====================
def resolve_exe(game: Dict[str, Any]) -> Optional[str]:
    exe = game.get("exe") or ""
    workdir = game.get("workdir") or ""
    if not exe:
        return None
    p = Path(exe)
    if p.is_absolute() and p.exists():
        return str(p)
    if workdir:
        candidate = Path(workdir) / exe
        if candidate.exists():
            return str(candidate)
    if p.exists():
        return str(p.resolve())
    return None


def launch_game(
        game: Dict[str, Any]) -> Optional[Tuple[subprocess.Popen, Path]]:
    exe = resolve_exe(game)
    if not exe:
        messagebox.showerror(
            "Ejecutable no encontrado",
            f"No se encontró el ejecutable.\n\n"
            f"exe: {game.get('exe')}\nworkdir: {game.get('workdir')}")
        return None

    env = os.environ.copy()
    if game.get("proton"):
        env["PROTONPATH"] = game["proton"]
    if game.get("prefix"):
        env["WINEPREFIX"] = game["prefix"]
        try:
            Path(game["prefix"]).mkdir(parents=True, exist_ok=True)
        except Exception:
            log.exception("launch_game: no se pudo crear el prefix %s",
                          game["prefix"])
    if game.get("gameid"):
        env["GAMEID"] = str(game["gameid"])
    if game.get("store"):
        env["STORE"] = game["store"]

    extra = game.get("extra_env", {})
    if isinstance(extra, str):
        for line in extra.strip().splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    elif isinstance(extra, dict):
        env.update(extra)

    cwd = game.get("workdir") or str(Path(exe).parent)
    if not Path(cwd).is_dir():
        messagebox.showerror("Directorio de trabajo inválido",
                             f"El directorio no existe:\n{cwd}")
        return None

    args = game.get("args", "")
    try:
        cmd_args = (shlex.split(args)
                    if isinstance(args, str) and args.strip() else (args or []))
    except ValueError:
        log.exception("launch_game: args inválidos, usando split simple: %r", args)
        cmd_args = args.split()

    umu = shutil.which("umu-run")
    if not umu:
        messagebox.showerror("umu-run no encontrado",
                             "umu-run no está en tu PATH.\nInstala umu-launcher.")
        return None

    cmd = [umu, exe] + cmd_args
    if game.get("inhibit", True) and shutil.which("systemd-inhibit"):
        cmd = ["systemd-inhibit", "--what=idle:sleep",
               f"--why=Playing {game.get('name', 'game')}",
               "--mode=block"] + cmd

    safe = re.sub(r'[^\w\-]+', '_', game.get("name", "game"))[:40]
    log_file = LOGS_DIR / f"{safe}_{os.urandom(3).hex()}.log"

    try:
        with open(log_file, "w", encoding="utf-8") as log_fh:
            log_fh.write("=== UmuLauncher log ===\n")
            log_fh.write(f"Game : {game.get('name')}\n")
            log_fh.write(f"Cmd  : {' '.join(cmd)}\n")
            log_fh.write(f"cwd  : {cwd}\n")
            log_fh.write(f"PROTONPATH: {env.get('PROTONPATH')}\n")
            log_fh.write(f"WINEPREFIX: {env.get('WINEPREFIX')}\n")
            log_fh.write(f"GAMEID    : {env.get('GAMEID')}\n")
            log_fh.write(f"STORE     : {env.get('STORE')}\n")
            log_fh.write("=" * 50 + "\n\n")
            log_fh.flush()

            proc = subprocess.Popen(
                cmd, env=env, cwd=cwd,
                stdout=log_fh, stderr=subprocess.STDOUT,
                start_new_session=True)

        # No bloqueamos la UI: la comprobación de fallo la hace el caller
        # con self.after() (ver UmuLauncherApp._finish_launch).
        return proc, log_file

    except Exception as e:
        log.exception("launch_game: fallo al lanzar %s", game.get("name"))
        messagebox.showerror("Error", f"Fallo al lanzar:\n{e}")
        return None
