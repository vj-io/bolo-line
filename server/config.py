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


def get_station(station_id: str):
    """The station dict, or None when the id is unknown."""
    return STATIONS.get(station_id)
