"""
Parseo de scripts .sh de umu-launcher y formateadores de tiempo de UmuLauncher.
"""

import os, re, time
from pathlib import Path
from typing import Dict, Any, List

from core.config import DEFAULT_EXTRA_ENV, DEFAULT_PROTON_PATHS


# ==================== Proton ====================
def find_protons() -> List[str]:
    protons, seen = [], set()
    for base in DEFAULT_PROTON_PATHS:
        if not base.exists():
            continue
        for item in sorted(base.iterdir()):
            if item.is_dir() and (item / "proton").exists():
                p = str(item)
                if p not in seen:
                    protons.append(p)
                    seen.add(p)
    return protons


# ==================== Formateadores ====================
def expand_path(value: str) -> str:
    value = value.strip().strip('"').strip("'")
    value = os.path.expandvars(value)
    value = os.path.expanduser(value)
    return value


def format_playtime(seconds: int) -> str:
    seconds = int(seconds or 0)
    if seconds < 60:
        return f"{seconds}s"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    if h > 0:
        return f"{h}h {m}m" if m else f"{h}h"
    return f"{m}m"


def format_last_played(ts: int) -> str:
    if not ts:
        return "nunca"
    delta = int(time.time()) - int(ts)
    if delta < 60:
        return "hace un momento"
    if delta < 3600:
        return f"hace {delta // 60} min"
    if delta < 86400:
        return f"hace {delta // 3600} h"
    if delta < 604800:
        n = delta // 86400
        return f"hace {n} día{'s' if n != 1 else ''}"
    if delta < 2592000:
        n = delta // 604800
        return f"hace {n} semana{'s' if n != 1 else ''}"
    return time.strftime("%d/%m/%Y", time.localtime(ts))


# ==================== Parse .sh ====================
LEGACY_ENV_BLACKLIST = {
    "XDG_CACHE_HOME", "DXVK_STATE_CACHE_PATH", "DXVK_HUD",
    "__GL_SHADER_DISK_CACHE", "__GL_SHADER_DISK_CACHE_PATH",
    "MESA_SHADER_CACHE_DISABLE", "MESA_GLSL_CACHE_DISABLE",
    "WINEDLLOVERRIDES", "WINEARCH", "WINEDEBUG",
}


def parse_sh_script(path: str) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "name": Path(path).stem,
        "exe": "", "workdir": "", "args": "",
        "proton": "", "prefix": "", "gameid": "",
        "store": "steam", "cover": "",
        "extra_env": "", "inhibit": True,
        "id": os.urandom(8).hex(),
        "last_played": 0, "total_playtime": 0,
    }
    extra_lines = []
    content = Path(path).read_text(encoding="utf-8", errors="ignore")

    m = re.search(r"#\s*={2,}\s*(.+?)\s*={2,}", content)
    if m:
        data["name"] = m.group(1).strip()
    else:
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("#") and not line.startswith("#!"):
                name = line.lstrip("#").strip()
                if name and len(name) > 3:
                    data["name"] = name
                    break

    logical_lines, buffer = [], ""
    for raw_line in content.splitlines():
        stripped = raw_line.rstrip()
        if stripped.endswith("\\"):
            buffer += stripped[:-1] + " "
        else:
            buffer += stripped
            logical_lines.append(buffer.strip())
            buffer = ""
    if buffer.strip():
        logical_lines.append(buffer.strip())

    for line in logical_lines:
        if not line:
            continue
        if line.startswith("export "):
            line = line[7:].strip()
            if "=" in line:
                key, val = line.split("=", 1)
                key, val = key.strip(), expand_path(val)
                if key == "PROTONPATH":
                    data["proton"] = val
                elif key == "WINEPREFIX":
                    data["prefix"] = val
                elif key == "GAMEID":
                    data["gameid"] = val
                elif key == "STORE":
                    data["store"] = val
                elif key in LEGACY_ENV_BLACKLIST:
                    pass
                else:
                    extra_lines.append(f"{key}={val}")
        elif line.startswith("cd ") or line.startswith("cd\t"):
            data["workdir"] = expand_path(line[2:].strip())
        elif "systemd-inhibit" in line:
            data["inhibit"] = True
        if "umu-run" in line:
            parts = re.split(r"\bumu-run\b", line, maxsplit=1)
            if len(parts) > 1:
                rest = parts[1].strip()
                tokens = re.findall(r'(?:[^\s"]|"(?:\\.|[^"])*")+', rest)
                if tokens:
                    data["exe"] = tokens[0].strip('"').strip("'")
                    if len(tokens) > 1:
                        data["args"] = " ".join(t.strip('"') for t in tokens[1:])

    if data["exe"] and not Path(data["exe"]).is_absolute() and data["workdir"]:
        candidate = Path(data["workdir"]) / data["exe"]
        if candidate.exists():
            data["exe"] = str(candidate)

    data["extra_env"] = ("\n".join(extra_lines) if extra_lines
                         else "\n".join(f"{k}={v}" for k, v in DEFAULT_EXTRA_ENV.items()))
    return data
