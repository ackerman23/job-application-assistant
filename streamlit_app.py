"""Deprecated legacy prototype kept only for historical reference.

The active application is now the Flask dashboard + FastAPI MCP stack.
This file is intentionally not part of the supported runtime.
"""

raise RuntimeError(
    "This Streamlit prototype is deprecated. Use the active Flask dashboard and FastAPI MCP server instead: python main.py --mode all"
)

import json
import re
from datetime import datetime
import streamlit as st
from app.services.profile_manager import load_profile, save_profile
from app.models.schemas import CandidateProfile
from app.services.jd_analyzer import analyze_job
from app.services.matching_engine import match_job
from app.services.generation import company_document_stem, generate_cv_tex, generate_cover_letter, generate_change_log, generate_letter_tex, compile_pdf
from app.core.config import APPLICATIONS_DIR, OPENAI_API_KEY

st.set_page_config(page_title="Job Application Engine", page_icon="🧭", layout="wide")
st.title("Job Application Engine")
st.caption("Evidence first · local profile storage · generated files saved to this device")

try:
    profile = load_profile()
except Exception as exc:
    st.error(f"Could not load candidate profile: {exc}"); st.stop()

with st.sidebar:
    st.subheader("Candidate master profile")
    st.caption("Edit the JSON profile. It is stored locally and is the source of truth for generated claims.")
    profile_json = st.text_area("Profile JSON", value=profile.model_dump_json(indent=2), height=450, label_visibility="collapsed")
    if st.button("Save profile", use_container_width=True):
        try:
            updated = CandidateProfile.model_validate_json(profile_json)
            save_profile(updated)
            st.success("Profile saved.")
            st.rerun()
        except Exception as exc:
            st.error(f"Profile JSON is invalid: {exc}")
    st.caption(f"Evidence entries: {len(profile.skills) + len(profile.experience) + len(profile.projects)}")
    if OPENAI_API_KEY:
        st.success("OpenAI API key detected.")
    else:
        st.warning("OpenAI API key not detected. Add OPENAI_API_KEY to the project-root .env file (not .env.example), then restart Streamlit.")

st.subheader("1. Paste a job description")
job_text = st.text_area("Job description", height=240, placeholder="Paste the complete job description here…", label_visibility="collapsed")
applicant_notes = st.text_area(
    "Your reason for applying (optional)",
    placeholder="In your own words: what interests you about this company or role? Which real experience should the letter focus on? Leave blank if you prefer.",
    key="applicant_notes",
    height=100,
)
analyze = st.button("Analyze job", type="primary", disabled=len(job_text.strip()) < 30)
if analyze:
    for key in ("generated_folder", "cover_letter"):
        st.session_state.pop(key, None)
    st.session_state.job_analysis = analyze_job(job_text)
    st.session_state.job_text = job_text
    st.session_state.match_analysis = match_job(st.session_state.job_analysis, profile)
    from app.database.database import Application, SessionLocal
    with SessionLocal() as session:
        record = Application(company=st.session_state.job_analysis.company, position=st.session_state.job_analysis.position, job_description=job_text, match_summary=st.session_state.match_analysis.summary, status="REVIEW")
        session.add(record)
        session.commit()
        st.session_state.application_id = record.id

if "match_analysis" in st.session_state:
    job = st.session_state.job_analysis
    match = st.session_state.match_analysis
    st.divider()
    st.subheader("2. Review the evidence match")
    st.markdown(f"**{job.position or 'Position not detected'}**  ·  {job.company or 'Company not detected'}")
    st.metric("Evidence coverage", f"{match.score}%")
    st.write(match.summary)
    st.caption(f"Job requirement analysis: {job.analysis_method} · evidence matching: {match.analysis_method}")
    if job.analysis_warning:
        st.warning(job.analysis_warning)
    if match.analysis_warning:
        st.warning(match.analysis_warning)
    tabs = st.tabs(["Strong matches", "Transferable", "Familiarity", "Learning gaps"])
    from app.models.schemas import MatchType
    for tab, kind in zip(tabs, [MatchType.VERIFIED, MatchType.TRANSFERABLE, MatchType.FAMILIARITY, MatchType.MISSING]):
        with tab:
            selected = [m for m in match.matches if m.match_type == kind]
            if not selected: st.caption("None identified.")
            for m in selected:
                st.markdown(f"**{m.requirement}** · {m.importance}")
                if m.candidate_evidence:
                    for ev in m.candidate_evidence: st.caption("Evidence: " + ev)
                elif kind == MatchType.MISSING: st.caption("No evidence in the master profile. Do not claim this skill.")
                if m.recommended_wording: st.write("Suggested wording: " + m.recommended_wording)
                st.divider()
    selected_cv_additions = set()
    with st.expander("Human review: choose job skills to add", expanded=True):
        st.caption("Every extracted skill is selectable. Your choices control which matched requirements appear in the CV. Unsupported selections are visibly marked as unverified keywords, not experience.")
        for index, item in enumerate(match.matches):
            priority = "Required" if item.importance == "HIGH" else ("Preferred" if item.importance == "LOW" else "Relevant")
            st.markdown(f"**{item.requirement}** · {priority} · {item.match_type.value.title()}")
            for ev in item.candidate_evidence:
                st.caption("Evidence: " + ev)
            if item.match_type in (MatchType.MISSING, MatchType.CONFLICT):
                suggestion = f"Self-selected job keyword (not verified): {item.requirement}"
            elif item.match_type == MatchType.FAMILIARITY:
                suggestion = f"Familiarity with {item.requirement}"
            else:
                suggestion = item.recommended_wording or item.requirement
            st.write("Suggested CV wording: " + suggestion)
            key_part = re.sub(r"[^a-z0-9]+", "_", item.requirement.casefold()).strip("_")[:48]
            if st.checkbox("Include this suggestion in the CV", key=f"cv_add_{index}_{key_part}"):
                selected_cv_additions.add(item.requirement)
            st.divider()
    familiarity_matches = [m for m in match.matches if m.match_type == MatchType.FAMILIARITY]
    if familiarity_matches:
        with st.expander("Familiarity explained for this job"):
            st.caption("These notes appear only when the job description matches a familiarity skill in your profile. They are explanatory only; no approval is needed and your profile is not changed.")
            for item in familiarity_matches:
                st.markdown(f"**{item.requirement}**")
                st.write("Your profile marks this as familiarity. The job description includes a related requirement, so present this as study or foundational knowledge rather than professional experience.")
                for ev in item.candidate_evidence:
                    st.caption("Profile evidence: " + ev)
    else:
        st.caption("No profile familiarity items matched this job description.")
    reviewed_match = match
    cover_letter_match = match.model_copy(update={"matches": [m for m in match.matches if m.match_type not in (MatchType.MISSING, MatchType.CONFLICT, MatchType.TRANSFERABLE, MatchType.FAMILIARITY) or (m.match_type in (MatchType.TRANSFERABLE, MatchType.FAMILIARITY) and m.requirement in selected_cv_additions)]})
    reviewed_profile = profile
    st.subheader("3. Generate application files")
    st.info("The CV prioritizes profile-backed skills, experience, and projects for this job. Unsupported requirements stay out of the CV.")
    if OPENAI_API_KEY:
        st.caption("AI-assisted analysis sends the job description and relevant profile evidence to OpenAI. The AI can classify only claims supported by the supplied profile evidence.")
    if not (profile.skills or profile.experience or profile.projects):
        st.warning("Add verified candidate evidence in the sidebar before generating personalized application documents.")
    else:
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("Generate downloadable CV (PDF)"):
                st.session_state.pop("generated_folder", None)
                st.session_state.pop("current_cv_tex", None)
                st.session_state.pop("current_cv_pdf", None)
                key = datetime.now().strftime("%Y%m%d-%H%M%S")
                folder = APPLICATIONS_DIR / key; folder.mkdir(parents=True, exist_ok=True)
                tex = generate_cv_tex(reviewed_profile, job, reviewed_match, list(selected_cv_additions))
                tex_path = folder / "tailored_cv.tex"
                tex_path.write_text(tex, encoding="utf-8")
                pdf_path = tex_path.with_suffix(".pdf")
                try:
                    compile_pdf(tex_path)
                except Exception as exc:
                    st.error(f"CV source was saved, but PDF compilation failed: {exc}")
                (folder / "job_description.txt").write_text(st.session_state.job_text, encoding="utf-8")
                (folder / "job_analysis.json").write_text(job.model_dump_json(indent=2), encoding="utf-8")
                (folder / "match_analysis.json").write_text(reviewed_match.model_dump_json(indent=2), encoding="utf-8")
                (folder / "learning_plan.md").write_text("# Learning plan\n\n" + "\n".join(f"- **{x['skill']}** ({x['priority']}): {x['reason']} {x['recommended_learning']}" for x in match.learning_recommendations), encoding="utf-8")
                (folder / "change_log.md").write_text(generate_change_log(reviewed_match), encoding="utf-8")
                from app.database.database import Application, SessionLocal
                with SessionLocal() as session:
                    record = session.get(Application, st.session_state.application_id)
                    if record: record.cv_path = str(folder / "tailored_cv.tex"); session.commit()
                st.session_state.generated_folder = folder
                st.session_state.current_cv_tex = tex
                if pdf_path.exists():
                    st.session_state.current_cv_pdf = pdf_path.read_bytes()
                st.success(f"Saved {folder.relative_to(APPLICATIONS_DIR.parent)}")
        with c2:
            if st.button("Generate cover letter"):
                try:
                    letter = generate_cover_letter(reviewed_profile, job, cover_letter_match, applicant_notes)
                    st.session_state.cover_letter = letter
                    if "generated_folder" in st.session_state:
                        folder = st.session_state.generated_folder
                        (folder / "cover_letter.txt").write_text(letter, encoding="utf-8")
                        (folder / "cover_letter.tex").write_text(generate_letter_tex(letter, profile, job.company, job.position), encoding="utf-8")
                except Exception as exc: st.error(str(exc))
        with c3:
            if st.button("Generate complete application"):
                try:
                    st.session_state.pop("generated_folder", None)
                    st.session_state.pop("current_cv_tex", None)
                    st.session_state.pop("current_cv_pdf", None)
                    key = datetime.now().strftime("%Y%m%d-%H%M%S")
                    folder = APPLICATIONS_DIR / key; folder.mkdir(parents=True, exist_ok=True)
                    tex = generate_cv_tex(reviewed_profile, job, reviewed_match, list(selected_cv_additions))
                    tex_path = folder / "tailored_cv.tex"
                    tex_path.write_text(tex, encoding="utf-8")
                    pdf_path = tex_path.with_suffix(".pdf")
                    try:
                        compile_pdf(tex_path)
                    except Exception as exc:
                        st.error(f"CV source was saved, but PDF compilation failed: {exc}")
                    (folder / "job_description.txt").write_text(st.session_state.job_text, encoding="utf-8")
                    (folder / "job_analysis.json").write_text(job.model_dump_json(indent=2), encoding="utf-8")
                    (folder / "match_analysis.json").write_text(reviewed_match.model_dump_json(indent=2), encoding="utf-8")
                    (folder / "learning_plan.md").write_text("# Learning plan\n\n" + "\n".join(f"- **{x['skill']}** ({x['priority']}): {x['reason']} {x['recommended_learning']}" for x in match.learning_recommendations), encoding="utf-8")
                    (folder / "change_log.md").write_text(generate_change_log(reviewed_match), encoding="utf-8")
                    letter = generate_cover_letter(reviewed_profile, job, cover_letter_match, applicant_notes)
                    (folder / "cover_letter.txt").write_text(letter, encoding="utf-8")
                    (folder / "cover_letter.tex").write_text(generate_letter_tex(letter, profile, job.company, job.position), encoding="utf-8")
                    from app.database.database import Application, SessionLocal
                    with SessionLocal() as session:
                        record = session.get(Application, st.session_state.application_id)
                        if record: record.cv_path = str(folder / "tailored_cv.tex"); record.cover_letter_path = str(folder / "cover_letter.txt"); session.commit()
                    st.session_state.generated_folder = folder
                    st.session_state.current_cv_tex = tex
                    if pdf_path.exists():
                        st.session_state.current_cv_pdf = pdf_path.read_bytes()
                    st.session_state.cover_letter = letter
                    st.success(f"Application files saved in {folder.relative_to(APPLICATIONS_DIR.parent)}")
                except Exception as exc: st.error(str(exc))
    if "cover_letter" in st.session_state:
        st.text_area("Generated cover letter — review before use", st.session_state.cover_letter, height=300)
        letter_filename = f"{company_document_stem(job.company, 'Cover Letter')}.txt"
        st.download_button("Download cover letter", st.session_state.cover_letter, file_name=letter_filename)
    if "generated_folder" in st.session_state:
        folder = st.session_state.generated_folder
        tex_path = folder / "tailored_cv.tex"
        pdf_path = folder / "tailored_cv.pdf"
        current_cv_pdf = st.session_state.get("current_cv_pdf")
        current_cv_tex = st.session_state.get("current_cv_tex")
        resume_stem = company_document_stem(job.company, "Resume")
        if current_cv_pdf is not None:
            st.download_button("Download CV as PDF", current_cv_pdf, file_name=f"{resume_stem}.pdf", mime="application/pdf", type="primary")
        elif pdf_path.exists():
            st.download_button("Download CV as PDF", pdf_path.read_bytes(), file_name=f"{resume_stem}.pdf", mime="application/pdf", type="primary")
        if not pdf_path.exists() and st.button("Compile CV PDF"):
            try:
                compile_pdf(tex_path)
                st.session_state.current_cv_pdf = pdf_path.read_bytes()
                st.rerun()
            except Exception as exc: st.error(str(exc))
        with st.expander("LaTeX source"):
            if current_cv_tex is not None:
                st.download_button("Download CV source (.tex)", current_cv_tex, file_name=f"{resume_stem}.tex")
            else:
                st.download_button("Download CV source (.tex)", tex_path.read_text(encoding="utf-8"), file_name=f"{resume_stem}.tex")
        letter_tex_path = folder / "cover_letter.tex"
        if letter_tex_path.exists() and st.button("Compile cover letter PDF"):
            try:
                letter_pdf = compile_pdf(letter_tex_path)
                st.download_button("Download cover letter PDF", letter_pdf.read_bytes(), file_name=f"{company_document_stem(job.company, 'Cover Letter')}.pdf", mime="application/pdf")
            except Exception as exc: st.error(str(exc))

with st.expander("Application history"):
    from app.database.database import Application, SessionLocal
    with SessionLocal() as session:
        history = session.query(Application).order_by(Application.date.desc()).all()
        if history:
            for item in history:
                left, right = st.columns([4, 1])
                with left:
                    st.write(f"{item.date:%Y-%m-%d} · {item.company or 'Unknown company'} · {item.position or 'Unknown position'}")
                    st.caption(item.match_summary)
                    if item.cv_path: st.caption(f"CV: {item.cv_path}")
                    if item.cover_letter_path: st.caption(f"Cover letter: {item.cover_letter_path}")
                with right:
                    statuses = ["DRAFT", "REVIEW", "APPLIED", "INTERVIEW", "REJECTED", "OFFER"]
                    current = item.status if item.status in statuses else "DRAFT"
                    new_status = st.selectbox("Status", statuses, index=statuses.index(current), key=f"status_{item.id}")
                    if new_status != item.status:
                        item.status = new_status
                        session.commit()
        else: st.caption("No applications analyzed yet.")
