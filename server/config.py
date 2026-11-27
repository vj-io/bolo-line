"""Runtime settings and the three read-only JSON files (station, samples, prompts)."""
import json
import os
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parent
WEB_DIR = SERVER_DIR.parent / "web"


def data_dir() -> Path:
    """Database and stored audio live here. Read on every call so tests can point it elsewhere."""
    default = "/tmp/bolo" if os.environ.get("VERCEL") else "./.data"  # a Vercel function can write only /tmp
    path = Path(os.environ.get("DATA_DIR", default))
    (path / "audio").mkdir(parents=True, exist_ok=True)
    return path


def sarvam_key() -> str:
    return os.environ.get("SARVAM_API_KEY", "").strip()


def _load(name: str):
    with open(SERVER_DIR / name, encoding="utf-8") as f:
        return json.load(f)


STATION = _load("stations.json")
SAMPLES = _load("samples.json")
# Templates: ask_machine uses {machines} / {machines_hi} (machine names joined with " ya " / " या ");
# confirm_machine uses {machine} / {machine_hi}; readback uses the four fields plus {machine_hi}.
PROMPTS = _load("prompts.json")
STATIONS = {STATION["id"]: STATION}


def _load_lang(path: Path):
    """One language pack (server/lang/<code>.json). Its generated number table, when it names one,
    is read here too, so nothing is opened after start-up."""
    pack = _load(f"lang/{path.name}")
    if pack["numbers"]["table"]:
        pack["numbers"]["table"] = _load(f"lang/{pack['numbers']['table']}")
    return pack


DEFAULT_LANG = "hi"
# Language packs by code, the default first: this is the order of the buttons on the operator screen.
LANGS = {pack["code"]: pack for pack in sorted(
    (_load_lang(p) for p in (SERVER_DIR / "lang").glob("*.json") if not p.name.startswith("numbers_")),
    key=lambda pack: (pack["code"] != DEFAULT_LANG, pack["code"]))}


def get_station(station_id: str):
    """The station dict, or None when the id is unknown."""
    return STATIONS.get(station_id)


def get_lang(code: str):
    """The language pack, or None when the code is unknown."""
    return LANGS.get(code)
