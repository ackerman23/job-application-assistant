from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TUTORIAL = (ROOT / "TUTORIAL.md").read_text(encoding="utf-8")


def test_tutorial_documents_the_supported_fresh_clone_workflow():
    assert "git clone https://github.com/ackerman23/job-application-assistant.git" in TUTORIAL
    assert "python scripts/setup.py install" in TUTORIAL
    assert "python scripts/setup.py run" in TUTORIAL
    assert "python scripts/setup.py init-profile" in TUTORIAL
    assert "python scripts/setup.py test" in TUTORIAL


def test_tutorial_references_tracked_setup_templates():
    assert (ROOT / ".env.example").is_file()
    assert (ROOT / "config" / "user-settings.example.yaml").is_file()
    assert (ROOT / "base-cv" / "candidate_profile.example.json").is_file()
    assert "config/user-settings.example.yaml" in TUTORIAL
    assert "base-cv/" in TUTORIAL
