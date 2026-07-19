import json
import os
import sys


def _passenger_defaults(rail: str) -> dict:
    if rail == "ktx":
        return {"adult": 1, "child": 0, "senior": 0, "toddler": 0}
    return {"adult": 1, "child": 0, "senior": 0,
            "disability1to3": 0, "disability4to6": 0}


def _defaults(rail: str) -> dict:
    return {
        "srt_id": "",
        "password": "",
        "dep_station": "서울" if rail == "ktx" else "동대구",
        "arr_station": "부산" if rail == "ktx" else "수서",
        "date": "",
        "time_from": "000000",
        "time_to": "230000",
        "passengers": _passenger_defaults(rail),
        "seat_type": "일반우선",
        "window_seat": False,
        "retry_interval": 0.8,
        "discord_webhook": "",
    }


def _frozen_base() -> str:
    base = os.path.dirname(sys.executable)
    # macOS .app 번들 내부(Contents/MacOS)라면 번들 바깥(.app 옆)에 저장한다
    parts = base.split(os.sep)
    if (len(parts) >= 3 and parts[-1] == "MacOS"
            and parts[-2] == "Contents" and parts[-3].endswith(".app")):
        base = os.sep.join(parts[:-3]) or os.sep
    return base


def _config_path(rail: str) -> str:
    env_dir = os.environ.get("SRTMACRO_CONFIG_DIR")
    if env_dir:
        base = env_dir
    elif getattr(sys, "frozen", False):
        base = _frozen_base()
    else:
        base = os.path.dirname(os.path.abspath(__file__))
        base = os.path.join(base, "..", "..")
    return os.path.normpath(os.path.join(base, f"config.{rail}.json"))


def load_config(rail: str = "srt") -> dict:
    defaults = _defaults(rail)
    path = _config_path(rail)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            saved = json.load(f)
        merged = {**defaults, **saved}
        merged["passengers"] = {**defaults["passengers"],
                                **saved.get("passengers", {})}
        return merged
    return {**defaults, "passengers": {**defaults["passengers"]}}


def save_config(cfg: dict, rail: str = "srt"):
    path = _config_path(rail)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
