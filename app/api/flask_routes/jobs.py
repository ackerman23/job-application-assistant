"""Job routes for the Flask app."""

from flask import Blueprint, jsonify, request
from app.services.workflow import analyze_job_description

jobs_bp = Blueprint("jobs", __name__, url_prefix="/jobs")


@jobs_bp.post("/analyze")
def analyze_job_route():
    payload = request.get_json(silent=True) or {}
    text = payload.get("text") or payload.get("job_description") or ""
    if len(text.strip()) < 30:
        return jsonify({"error": "Job description is too short."}), 400
    try:
        return jsonify(analyze_job_description(text).model_dump(mode="json"))
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503


@jobs_bp.get("/")
def list_jobs():
    return jsonify({"status": "not_implemented", "message": "Job history listing will be implemented here."})
