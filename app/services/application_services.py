"""Application-level services shared by the Flask UI and API layers.

These services keep HTTP routes focused on request parsing and responses while
centralizing workflow and document-export behavior.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Callable

from app.core.config import APPLICATIONS_DIR
from app.core.settings import resolve_document_language
from app.models.schemas import CandidateProfile, JobAnalysis, MatchAnalysis, MatchType
from app.services.generation import (
    company_document_stem,
    compile_pdf,
    generate_letter_tex,
    validate_cover_letter_style,
)
from app.services.workflow import (
    analyze_profile_for_job,
    generate_cover_letter_document,
    generate_cv_document,
)


class ApplicationWorkflowService:
    """Coordinate analysis and CV generation for one application draft."""

    def __init__(
        self,
        analyze: Callable = analyze_profile_for_job,
        generate_cv: Callable = generate_cv_document,
    ) -> None:
        self._analyze = analyze
        self._generate_cv = generate_cv

    def analyze_or_restore(
        self,
        profile: CandidateProfile,
        job_text: str,
        action: str,
        job_analysis_json: str = "",
        match_analysis_json: str = "",
    ) -> tuple[JobAnalysis, MatchAnalysis, list[str]]:
        stateful_actions = {
            "download_pdf",
            "download_tex",
            "generate_cover_letter",
            "download_cover_letter_pdf",
            "download_cover_letter_tex",
            "download_cover_letter_txt",
        }
        if action in stateful_actions:
            if not job_analysis_json or not match_analysis_json:
                raise ValueError("Please analyze the job first, then download the reviewed CV.")
            job = JobAnalysis.model_validate_json(job_analysis_json)
            match = MatchAnalysis.model_validate_json(match_analysis_json)
            selected = []
        else:
            job, match = self._analyze(profile, job_text)
            selected = [
                item.requirement
                for item in match.matches
                if item.match_type not in (MatchType.MISSING, MatchType.CONFLICT)
            ]
        return job, match, selected

    def generate_cv(
        self,
        profile: CandidateProfile,
        job: JobAnalysis,
        match: MatchAnalysis,
        selected_requirements: list[str],
    ) -> str:
        return self.generate_cv_document(profile, job, match, selected_requirements)["cv_latex"]

    def generate_cv_document(
        self,
        profile: CandidateProfile,
        job: JobAnalysis,
        match: MatchAnalysis,
        selected_requirements: list[str] | None = None,
    ) -> dict[str, str]:
        return self._generate_cv(profile, job, match, selected_requirements)


class CoverLetterService:
    """Generate and quality-check cover-letter drafts."""

    def __init__(self, generate: Callable = generate_cover_letter_document) -> None:
        self._generate = generate

    def generate(
        self,
        profile: CandidateProfile,
        job: JobAnalysis,
        match: MatchAnalysis,
        applicant_notes: str = "",
    ) -> tuple[str, list[str]]:
        text = self._generate(profile, job, match, applicant_notes)
        return text, validate_cover_letter_style(text)


class DocumentExportService:
    """Create company-named CV and cover-letter export files."""

    def __init__(
        self,
        applications_dir: Path = APPLICATIONS_DIR,
        compile: Callable = compile_pdf,
        render_letter: Callable = generate_letter_tex,
    ) -> None:
        self.applications_dir = applications_dir
        self._compile = compile
        self._render_letter = render_letter

    def _work_dir(self, prefix: str) -> Path:
        return Path(tempfile.mkdtemp(prefix=prefix, dir=self.applications_dir))

    def cover_letter(
        self,
        text: str,
        profile: CandidateProfile,
        job: JobAnalysis,
        action: str,
    ) -> tuple[Path, str]:
        work_dir = self._work_dir("cover-letter-download-")
        stem = company_document_stem(job.company, "Cover Letter")
        txt_path = work_dir / f"{stem}.txt"
        tex_path = work_dir / f"{stem}.tex"
        txt_path.write_text(text, encoding="utf-8")
        language = resolve_document_language(job.job_language)
        rendered_letter = (
            self._render_letter(text, profile, job.company, job.position)
            if language == "English"
            else self._render_letter(text, profile, job.company, job.position, language)
        )
        tex_path.write_text(rendered_letter, encoding="utf-8")
        if action == "download_cover_letter_txt":
            return txt_path, f"{stem}.txt"
        if action == "download_cover_letter_tex":
            return tex_path, f"{stem}.tex"
        try:
            return self._compile(tex_path), f"{stem}.pdf"
        except Exception:
            shutil.rmtree(work_dir, ignore_errors=True)
            raise

    def cv(
        self,
        latex: str,
        job: JobAnalysis,
        selected_learning: dict,
        action: str,
    ) -> tuple[Path, str]:
        work_dir = self._work_dir("cv-download-")
        tex_path = work_dir / "tailored_cv.tex"
        tex_path.write_text(latex, encoding="utf-8")
        self.save_learning_plan(work_dir, selected_learning)
        if action == "download_tex":
            return tex_path, f"{company_document_stem(job.company, 'Resume')}.tex"
        try:
            return self._compile(tex_path), f"{company_document_stem(job.company, 'Resume')}.pdf"
        except Exception:
            shutil.rmtree(work_dir, ignore_errors=True)
            raise

    @staticmethod
    def save_learning_plan(folder: Path, selected_learning: dict) -> None:
        lines = [
            "# Learning plan",
            "",
            "Selected job requirements without supporting profile evidence:",
            "",
        ]
        if selected_learning:
            lines.extend(
                f"- **{item.requirement}** ({item.importance} priority) — selected for learning; not included as a CV claim."
                for item in selected_learning.values()
            )
        else:
            lines.append("- No unsupported requirements were selected.")
        folder.joinpath("learning_plan.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
