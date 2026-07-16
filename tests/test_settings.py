import os
import json
import src.config.settings as settings


def test_config_path_per_rail():
    p_srt = settings._config_path("srt")
    p_ktx = settings._config_path("ktx")
    assert p_srt.endswith("config.srt.json")
    assert p_ktx.endswith("config.ktx.json")


def test_ktx_passenger_defaults_have_toddler_no_disability():
    d = settings._passenger_defaults("ktx")
    assert "toddler" in d
    assert "disability1to3" not in d


def test_srt_passenger_defaults_have_disability():
    d = settings._passenger_defaults("srt")
    assert "disability1to3" in d
    assert "toddler" not in d


def test_save_then_load_roundtrip(tmp_path, monkeypatch):
    target = tmp_path / "config.ktx.json"
    monkeypatch.setattr(settings, "_config_path", lambda rail: str(target))
    settings.save_config({"srt_id": "123", "dep_station": "서울",
                          "passengers": {"adult": 2}}, "ktx")
    loaded = settings.load_config("ktx")
    assert loaded["srt_id"] == "123"
    assert loaded["dep_station"] == "서울"
    assert loaded["passengers"]["adult"] == 2
    assert loaded["passengers"]["toddler"] == 0
