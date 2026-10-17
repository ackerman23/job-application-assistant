import pytest

from app.models.schemas import JobAnalysis, MatchAnalysis
from app.services import tracker


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(tracker, "DB_PATH", tmp_path / "tracker.db")


def _job(company="Acme", position="Dev"):
    return JobAnalysis(company=company, position=position), MatchAnalysis(score=72)


def test_same_job_text_updates_instead_of_duplicating():
    job, match = _job()
    first = tracker.save_analysis("We need Python.", job, match, ["Python"])
    second = tracker.save_analysis("  we   need python. ", job, MatchAnalysis(score=80), ["Python", "SQL"])
    assert first == second
    rows = tracker.list_applications()
    assert len(rows) == 1 and rows[0]["score"] == 80


def test_letter_selection_status_notes_and_documents_roundtrip():
    job, match = _job()
    app_id = tracker.save_analysis("Job text", job, match, ["Python"])
    tracker.update_for_job("Job text", cover_letter="Dear team", selected_json='["Python"]')
    tracker.record_document("Job text", "Acme Resume.pdf")
    assert tracker.set_status(app_id, "Applied")
    assert tracker.set_notes(app_id, "Call on Monday")
    saved = tracker.get_application(app_id)
    assert saved["cover_letter"] == "Dear team"
    assert saved["status"] == "Applied" and saved["notes"] == "Call on Monday"
    assert saved["documents"][0]["label"] == "Acme Resume.pdf"
    assert JobAnalysis.model_validate_json(saved["job_json"]).company == "Acme"


def test_invalid_status_is_rejected():
    app_id = tracker.save_analysis("Job", *_job())
    with pytest.raises(ValueError):
        tracker.set_status(app_id, "Hired!!")


def test_filter_search_and_delete():
    a = tracker.save_analysis("Job A", *_job("Airbus", "Engineer"))
    tracker.save_analysis("Job B", *_job("Thales", "Analyst"))
    tracker.set_status(a, "Interview")
    assert [r["company"] for r in tracker.list_applications(status="Interview")] == ["Airbus"]
    assert [r["company"] for r in tracker.list_applications(query="thal")] == ["Thales"]
    assert tracker.delete_application(a) and tracker.get_application(a) is None


def test_safe_wrapper_swallows_errors():
    def boom():
        raise RuntimeError("disk full")
    assert tracker.safe(boom) is None


def _client(monkeypatch):
    from tests.test_dashboard_cv_download import _sample_profile, _sample_job_and_match
    from app.flask_app import app
    profile = _sample_profile()
    job, match = _sample_job_and_match()
    monkeypatch.setattr("app.flask_app.load_profile", lambda: profile)
    monkeypatch.setattr("app.flask_app.save_profile", lambda value: None)
    monkeypatch.setattr("app.flask_app.analyze_profile_for_job", lambda p, t: (job, match))
    return app.test_client(), profile


JOB_TEXT = "A sufficiently long job description for this test."


def test_analyze_saves_lists_and_reopens(monkeypatch):
    client, profile = _client(monkeypatch)
    r = client.post("/dashboard", data={"profile_json": profile.model_dump_json(), "job_text": JOB_TEXT})
    assert r.status_code == 200
    page = client.get("/applications")
    assert b"Airbus" in page.data
    app_id = tracker.list_applications()[0]["id"]
    reopened = client.get(f"/dashboard?application={app_id}")
    assert reopened.status_code == 200 and b"Airbus" in reopened.data
    assert client.post(f"/applications/{app_id}/status", data={"status": "Applied"}).status_code == 302
    assert client.post("/applications/999/delete").status_code == 404
    assert client.post(f"/applications/{app_id}/status", data={"status": "x"}).status_code == 400


def test_tracker_failure_does_not_break_analysis(monkeypatch):
    client, profile = _client(monkeypatch)
    monkeypatch.setattr(tracker, "DB_PATH", "/nonexistent/dir/x.db")
    r = client.post("/dashboard", data={"profile_json": profile.model_dump_json(), "job_text": JOB_TEXT})
    assert r.status_code == 200 and b'name="job_analysis_json"' in r.data
