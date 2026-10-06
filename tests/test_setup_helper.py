import importlib.util
from pathlib import Path


SETUP_PATH = Path(__file__).resolve().parents[1] / "scripts" / "setup.py"
spec = importlib.util.spec_from_file_location("setup_helper", SETUP_PATH)
setup_helper = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(setup_helper)


def test_env_has_openai_key_accepts_configured_key(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_API_KEY=configured-key\n", encoding="utf-8")
    monkeypatch.setattr(setup_helper, "ENV_FILE", env_file)

    assert setup_helper.env_has_openai_key()


def test_env_has_openai_key_rejects_blank_key(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_API_KEY=\n", encoding="utf-8")
    monkeypatch.setattr(setup_helper, "ENV_FILE", env_file)

    assert not setup_helper.env_has_openai_key()


def test_init_profile_copies_fictional_starter_without_overwriting(tmp_path, monkeypatch):
    profile_file = tmp_path / "data" / "candidate_profile.json"
    monkeypatch.setattr(setup_helper, "PROFILE_FILE", profile_file)

    setup_helper.init_profile(force=False)

    assert profile_file.read_text(encoding="utf-8") == setup_helper.PROFILE_TEMPLATE.read_text(encoding="utf-8")

    try:
        setup_helper.init_profile(force=False)
    except SystemExit as exc:
        assert "already exists" in str(exc)
    else:
        raise AssertionError("Expected an existing private profile to be preserved")
