import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    ROOT = Path(__file__).resolve().parents[1]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

from flask import Flask, abort, jsonify, redirect, render_template, request, send_file, url_for

from app.api.flask_routes import documents_bp, jobs_bp, profiles_bp
from app.core.config import APPLICATIONS_DIR
from app.core.settings import resolve_document_language
from app.models.schemas import CandidateProfile, JobAnalysis, MatchAnalysis, MatchType
from app.services import tracker, voice
from app.services.application_services import (
    ApplicationWorkflowService,
    CoverLetterService,
    DocumentExportService,
)
from app.services.generation import compile_pdf, generate_letter_tex
from app.services.profile_manager import load_profile, save_profile
from app.services.workflow import analyze_profile_for_job, generate_cover_letter_document, generate_cv_document


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates")
    app.register_blueprint(profiles_bp)
    app.register_blueprint(jobs_bp)
    app.register_blueprint(documents_bp)

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/dashboard")
    @app.post("/dashboard")
    def dashboard():
        profile = load_profile()
        job_analysis = None
        match_analysis = None
        cv_latex = None
        error = None
        profile_json = profile.model_dump_json(indent=2)
        job_text = ""
        selected_requirements = []
        selected_learning_requirements = []
        job_analysis_json = ""
        match_analysis_json = ""
        cover_letter_text = ""
        cover_letter_style_notes = []
        applicant_notes = ""
        company_url = ""

        reopen_id = request.args.get("application", type=int) if request.method == "GET" else None
        if reopen_id is not None:
            saved = tracker.safe(tracker.get_application, reopen_id)
            if saved is None:
                error = "That saved application no longer exists."
            else:
                job_text = saved["job_text"]
                job_analysis = JobAnalysis.model_validate_json(saved["job_json"])
                match_analysis = MatchAnalysis.model_validate_json(saved["match_json"])
                job_analysis_json, match_analysis_json = saved["job_json"], saved["match_json"]
                selected_requirements = saved["selected"]
                cover_letter_text = saved["cover_letter"]
                # The template only needs a truthy value to show the document actions;
                # the CV itself is regenerated from the saved analysis on download.
                cv_latex = "reopened"

        if request.method == "POST":
            profile_json = request.form.get("profile_json", profile_json)
            job_text = request.form.get("job_text", "")
            action = request.form.get("action", "analyze")
            selected_requirements = request.form.getlist("selected_requirements")
            selected_learning_requirements = request.form.getlist("learning_requirements")
            cover_letter_text = request.form.get("cover_letter_text", "")
            applicant_notes = request.form.get("applicant_notes", "")
            company_url = request.form.get("company_url", "").strip()

            try:
                profile = CandidateProfile.model_validate_json(profile_json)
                save_profile(profile)
            except Exception as exc:
                error = f"Profile JSON is invalid: {exc}"

            if not error and not job_text.strip():
                error = "Paste a job description before running this step."

            if not error and job_text.strip():
                try:
                    job_analysis_json = request.form.get("job_analysis_json", "")
                    match_analysis_json = request.form.get("match_analysis_json", "")
                    workflow = ApplicationWorkflowService(
                        analyze=analyze_profile_for_job,
                        generate_cv=generate_cv_document,
                    )
                    job_analysis, match_analysis, analyzed_requirements = workflow.analyze_or_restore(
                        profile,
                        job_text,
                        action,
                        job_analysis_json,
                        match_analysis_json,
                    )
                    if not selected_requirements:
                        selected_requirements = analyzed_requirements
                    job_analysis_json = job_analysis.model_dump_json()
                    match_analysis_json = match_analysis.model_dump_json()
                    if action == "analyze":
                        tracker.safe(tracker.save_analysis, job_text, job_analysis, match_analysis, selected_requirements)
                    else:
                        tracker.safe(
                            tracker.update_for_job, job_text,
                            selected_json=json.dumps(selected_requirements, ensure_ascii=False),
                        )
                    cv_latex = workflow.generate_cv(profile, job_analysis, match_analysis, selected_requirements)

                    if action == "generate_cover_letter":
                        cover_letter_text, cover_letter_style_notes = CoverLetterService(
                            generate=generate_cover_letter_document,
                        ).generate(profile, job_analysis, match_analysis, applicant_notes, job_text, company_url)
                        tracker.safe(tracker.update_for_job, job_text, cover_letter=cover_letter_text)

                    if action in {"download_cover_letter_pdf", "download_cover_letter_tex", "download_cover_letter_txt"}:
                        if not cover_letter_text.strip():
                            raise ValueError("Generate and review the cover letter before downloading it.")
                        export = DocumentExportService(
                            applications_dir=APPLICATIONS_DIR,
                            compile=compile_pdf,
                            render_letter=generate_letter_tex,
                        )
                        file_path, download_name = export.cover_letter(
                            cover_letter_text, profile, job_analysis, action
                        )
                        tracker.safe(tracker.record_document, job_text, download_name)
                        return send_file(file_path, as_attachment=True, download_name=download_name)

                    selected_learning = {
                        item.requirement: item
                        for item in match_analysis.matches
                        if item.requirement in selected_learning_requirements
                        and item.match_type in (MatchType.MISSING, MatchType.CONFLICT)
                    }

                    if action == "download_pdf":
                        export = DocumentExportService(
                            applications_dir=APPLICATIONS_DIR,
                            compile=compile_pdf,
                        )
                        selected_learning = {
                            item.requirement: item
                            for item in match_analysis.matches
                            if item.requirement in selected_learning_requirements
                            and item.match_type in (MatchType.MISSING, MatchType.CONFLICT)
                        }
                        file_path, download_name = export.cv(
                            cv_latex, job_analysis, selected_learning, action
                        )
                        tracker.safe(tracker.record_document, job_text, download_name)
                        return send_file(file_path, as_attachment=True, download_name=download_name)

                    if action == "download_tex":
                        export = DocumentExportService(
                            applications_dir=APPLICATIONS_DIR,
                            compile=compile_pdf,
                        )
                        selected_learning = {
                            item.requirement: item
                            for item in match_analysis.matches
                            if item.requirement in selected_learning_requirements
                            and item.match_type in (MatchType.MISSING, MatchType.CONFLICT)
                        }
                        file_path, download_name = export.cv(
                            cv_latex, job_analysis, selected_learning, action
                        )
                        tracker.safe(tracker.record_document, job_text, download_name)
                        return send_file(file_path, as_attachment=True, download_name=download_name)

                except Exception as exc:
                    if action == "generate_cover_letter":
                        error = f"Could not generate the cover letter: {exc}"
                    elif action in {"download_cover_letter_pdf", "download_cover_letter_tex", "download_cover_letter_txt"}:
                        error = f"Could not download the cover letter: {exc}"
                    elif action in {"download_pdf", "download_tex"}:
                        error = f"Could not generate or download the CV: {exc}"
                    else:
                        error = f"Could not analyze the job or generate the CV: {exc}"

        return render_template(
            "dashboard.html",
            profile_json=profile_json,
            job_text=job_text,
            job_analysis=job_analysis,
            match_analysis=match_analysis,
            cv_latex=cv_latex,
            selected_requirements=selected_requirements,
            selected_learning_requirements=selected_learning_requirements,
            job_analysis_json=job_analysis_json,
            match_analysis_json=match_analysis_json,
            cover_letter_text=cover_letter_text,
            cover_letter_style_notes=cover_letter_style_notes,
            document_language=resolve_document_language(job_analysis.job_language) if job_analysis else "English",
            applicant_notes=applicant_notes,
            company_url=company_url,
            error=error,
        )

    @app.get("/applications")
    def applications():
        status = request.args.get("status", "")
        query = request.args.get("q", "")
        return render_template(
            "applications.html",
            applications=tracker.safe(tracker.list_applications, status, query) or [],
            statuses=tracker.STATUSES,
            active_status=status,
            query=query,
        )

    @app.post("/applications/<int:application_id>/status")
    def application_status(application_id: int):
        try:
            if not tracker.set_status(application_id, request.form.get("status", "")):
                abort(404)
        except ValueError:
            abort(400)
        return redirect(url_for("applications"))

    @app.post("/applications/<int:application_id>/notes")
    def application_notes(application_id: int):
        if not tracker.set_notes(application_id, request.form.get("notes", "")):
            abort(404)
        return redirect(url_for("applications"))

    @app.post("/applications/<int:application_id>/delete")
    def application_delete(application_id: int):
        if not tracker.delete_application(application_id):
            abort(404)
        return redirect(url_for("applications"))

    @app.route("/voice", methods=["GET", "POST"])
    def voice_page():
        saved = False
        if request.method == "POST":
            voice.save_samples(voice.split_samples(request.form.get("samples", "")))
            saved = True
        samples = voice.load_samples()
        return render_template(
            "voice.html",
            samples_text="\n\n---\n\n".join(samples),
            profile=voice.analyze(samples),
            saved=saved,
        )

    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "service": "flask"})

    return app


app = create_app()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Flask job-application UI.")
    parser.add_argument("--port", type=int, default=5000, help="Port for the Flask server.")
    parser.add_argument("--debug", action="store_true", help="Run Flask in debug mode.")
    args = parser.parse_args()
    app.run(host="0.0.0.0", port=args.port, debug=args.debug)
