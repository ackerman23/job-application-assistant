from pathlib import Path

from fastapi import BackgroundTasks

from app.api import routes_documents
from app.api.flask_routes import documents as flask_documents
from app.api.fastapi_mcp import server as mcp_server
from app.mcp import adapters
from app.mcp.registry import list_tools
from app.models.schemas import CandidateProfile, JobAnalysis, MatchAnalysis
from app.services.generation import generate_letter_tex
from app.flask_app import app


def _profile() -> CandidateProfile:
    return CandidateProfile(
        personal={"name": "Test Candidate", "email": "test@example.com", "phone": "+49 123"},
    )


def _job() -> JobAnalysis:
    return JobAnalysis(company="Example & Sons", position="Research Engineer")


def test_cover_letter_tex_template_has_company_role_candidate_and_body():
    tex = generate_letter_tex(
        "The role's satellite systems focus matches my documented project experience.\n\nI built and tested a ground-segment prototype.",
        _profile(),
        _job().company,
        _job().position,
    )

    assert r"Cover Letter for Example \& Sons" in tex
    assert r"Re: Research Engineer" in tex
    assert "Test Candidate" in tex
    assert "test@example.com" in tex
    assert "satellite systems focus" in tex
    assert r"\begin{document}" in tex
    assert r"\end{document}" in tex


def test_dashboard_can_generate_and_review_company_specific_letter(monkeypatch):
    profile = _profile()
    job = _job()
    match = MatchAnalysis()
    letter = "The role's research focus matches my documented project work.\n\nI built and tested a satellite ground-segment prototype.\n\nI would welcome a conversation about the position."
    received_notes = []
    monkeypatch.setattr("app.flask_app.load_profile", lambda: profile)
    monkeypatch.setattr("app.flask_app.save_profile", lambda value: None)
    monkeypatch.setattr("app.flask_app.analyze_profile_for_job", lambda profile, text: (job, match))
    monkeypatch.setattr("app.flask_app.generate_cover_letter_document", lambda profile, job, match, notes="": received_notes.append(notes) or letter)

    response = app.test_client().post(
        "/dashboard",
        data={
            "action": "generate_cover_letter",
            "profile_json": profile.model_dump_json(),
            "job_text": "A sufficiently long job description for this test.",
            "job_analysis_json": job.model_dump_json(),
            "match_analysis_json": match.model_dump_json(),
            "applicant_notes": "I want to connect my satellite project work to this research role.",
        },
    )

    assert response.status_code == 200
    assert b"Cover letter for Example &amp; Sons" in response.data
    assert b"Download cover letter PDF" in response.data
    assert b"The role&#39;s research focus" in response.data
    assert received_notes == ["I want to connect my satellite project work to this research role."]


def test_dashboard_shows_short_cover_letter_with_non_blocking_style_suggestions(monkeypatch):
    profile = _profile()
    job = _job()
    match = MatchAnalysis()
    monkeypatch.setattr("app.flask_app.load_profile", lambda: profile)
    monkeypatch.setattr("app.flask_app.save_profile", lambda value: None)
    monkeypatch.setattr("app.flask_app.generate_cover_letter_document", lambda profile, job, match, notes="": "Short but role-specific draft.")

    response = app.test_client().post(
        "/dashboard",
        data={
            "action": "generate_cover_letter",
            "profile_json": profile.model_dump_json(),
            "job_text": "A sufficiently long job description for this test.",
            "job_analysis_json": job.model_dump_json(),
            "match_analysis_json": match.model_dump_json(),
            "applicant_notes": "I like this team's satellite research.",
        },
    )

    assert b"Cover letter draft" in response.data
    assert b"Short but role-specific draft." in response.data
    assert b"Optional editing suggestions" in response.data
    assert "words" in response.get_data(as_text=True)
    assert b"Could not generate the cover letter" not in response.data


def test_dashboard_downloads_company_specific_cover_letter_pdf(tmp_path, monkeypatch):
    profile = _profile()
    job = _job()
    match = MatchAnalysis()
    monkeypatch.setattr("app.flask_app.load_profile", lambda: profile)
    monkeypatch.setattr("app.flask_app.save_profile", lambda value: None)
    monkeypatch.setattr("app.flask_app.APPLICATIONS_DIR", tmp_path)

    def fake_compile(tex_path: Path) -> Path:
        pdf_path = tex_path.with_suffix(".pdf")
        pdf_path.write_bytes(b"%PDF-1.4 test")
        return pdf_path

    monkeypatch.setattr("app.flask_app.compile_pdf", fake_compile)
    response = app.test_client().post(
        "/dashboard",
        data={
            "action": "download_cover_letter_pdf",
            "profile_json": profile.model_dump_json(),
            "job_text": "A sufficiently long job description for this test.",
            "job_analysis_json": job.model_dump_json(),
            "match_analysis_json": match.model_dump_json(),
            "cover_letter_text": "The role matches my evidence.\n\nI built a relevant project.\n\nI welcome a conversation.",
        },
    )

    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.data.startswith(b"%PDF")
    assert "Example Sons Cover Letter.pdf" in response.headers["Content-Disposition"]
    tex_path = next(Path(tmp_path).glob("cover-letter-download-*/*.tex"))
    assert r"Cover Letter for Example \& Sons" in tex_path.read_text(encoding="utf-8")


def test_mcp_cover_letter_tool_returns_text_and_company_heading(monkeypatch):
    profile = _profile()
    job = _job()
    received_notes = []
    monkeypatch.setattr(adapters, "generate_cover_letter_document", lambda profile, job, match, notes="": received_notes.append(notes) or "A tailored letter body.")

    result = adapters.adapt_cover_letter_service(profile, job, MatchAnalysis(), "I value this research role.")

    assert result["text"] == "A tailored letter body."
    assert r"Cover Letter for Example \& Sons" in result["latex"]
    assert result["company"] == "Example & Sons"
    assert received_notes == ["I value this research role."]
    assert "documents.generate_cover_letter" in list_tools()
    assert "documents.generate_cover_letter_pdf" in list_tools()


def test_mcp_cover_letter_pdf_tool_returns_company_filename(tmp_path, monkeypatch):
    profile = _profile()
    job = _job()
    monkeypatch.setattr(adapters, "APPLICATIONS_DIR", tmp_path)
    monkeypatch.setattr(adapters, "generate_cover_letter_document", lambda profile, job, match, notes="": "A tailored letter.")

    def fake_compile(tex_path: Path) -> Path:
        pdf_path = tex_path.with_suffix(".pdf")
        pdf_path.write_bytes(b"%PDF-1.4 test")
        return pdf_path

    monkeypatch.setattr(adapters, "compile_pdf", fake_compile)
    result = adapters.adapt_cover_letter_pdf_service(profile, job, MatchAnalysis())

    assert result["filename"] == "Example Sons Cover Letter.pdf"
    assert Path(result["pdf_path"]).is_file()


def test_mcp_cv_pdf_tool_returns_company_filename(tmp_path, monkeypatch):
    profile = _profile()
    job = _job()
    monkeypatch.setattr(adapters, "APPLICATIONS_DIR", tmp_path)
    monkeypatch.setattr(adapters, "generate_cv_document", lambda profile, job, match, selected: {"cv_latex": "CV source", "change_log": "Changes"})

    def fake_compile(tex_path: Path) -> Path:
        pdf_path = tex_path.with_suffix(".pdf")
        pdf_path.write_bytes(b"%PDF-1.4 test")
        return pdf_path

    monkeypatch.setattr(adapters, "compile_pdf", fake_compile)
    result = adapters.adapt_cv_pdf_service(profile, job, MatchAnalysis())

    assert result["filename"] == "Example Sons Resume.pdf"
    assert result["change_log"] == "Changes"
    assert "cv.generate_cv_pdf" in list_tools()


def test_mcp_tool_route_includes_latex(monkeypatch):
    profile = _profile()
    job = _job()
    monkeypatch.setattr(mcp_server, "adapt_cover_letter_service", lambda profile, job, match, notes="": {"text": "Letter text", "latex": "Cover Letter for Example", "company": job.company, "position": job.position})

    result = mcp_server.generate_cover_letter_tool(
        mcp_server.CvPayload(profile=profile, job=job, match=MatchAnalysis())
    )

    assert result["text"] == "Letter text"
    assert result["latex"] == "Cover Letter for Example"


def test_rest_cover_letter_pdf_download_uses_company_filename(tmp_path, monkeypatch):
    profile = _profile()
    job = _job()
    monkeypatch.setattr(routes_documents, "APPLICATIONS_DIR", tmp_path)
    monkeypatch.setattr(routes_documents, "generate_cover_letter_document", lambda profile, job, match, notes="": "A tailored letter.")
    monkeypatch.setattr(routes_documents, "generate_letter_tex", lambda text, profile, company, position: "\\documentclass{article}\\begin{document}Letter\\end{document}")

    def fake_compile(tex_path: Path) -> Path:
        pdf_path = tex_path.with_suffix(".pdf")
        pdf_path.write_bytes(b"%PDF-1.4 test")
        return pdf_path

    monkeypatch.setattr(routes_documents, "compile_pdf", fake_compile)
    result = routes_documents.cover_letter_pdf(
        routes_documents.DocumentInput(profile=profile, job=job, match=MatchAnalysis()),
        BackgroundTasks(),
    )

    assert "filename*=utf-8''Example%20Sons%20Cover%20Letter.pdf" in result.headers["content-disposition"]


def test_rest_cover_letter_endpoint_forwards_applicant_notes(monkeypatch):
    profile = _profile()
    job = _job()
    match = MatchAnalysis()
    received_notes = []
    monkeypatch.setattr(flask_documents, "generate_cover_letter_document", lambda profile, job, match, notes="": received_notes.append(notes) or "A tailored letter.")
    monkeypatch.setattr(flask_documents, "generate_letter_tex", lambda text, profile, company, position: "letter latex")

    response = app.test_client().post(
        "/documents/generate-letter",
        json={
            "profile": profile.model_dump(mode="json"),
            "job": job.model_dump(mode="json"),
            "match": match.model_dump(mode="json"),
            "applicant_notes": "I want to work on this research area.",
        },
    )

    assert response.status_code == 200
    assert received_notes == ["I want to work on this research area."]
