"""Application routes for the Flask app."""

from flask import Blueprint, jsonify
from app.database.database import Application, SessionLocal

applications_bp = Blueprint("applications", __name__, url_prefix="/applications")


@applications_bp.get("/")
def list_applications():
    with SessionLocal() as session:
        rows = session.query(Application).order_by(Application.date.desc()).all()
    return jsonify([
        {
            "id": row.id,
            "company": row.company,
            "position": row.position,
            "date": row.date.isoformat(),
            "match_summary": row.match_summary,
            "cv_path": row.cv_path,
            "cover_letter_path": row.cover_letter_path,
            "status": row.status,
        }
        for row in rows
    ])


@applications_bp.get("/<application_id>")
def get_application(application_id):
    with SessionLocal() as session:
        row = session.get(Application, int(application_id))
    if row is None:
        return jsonify({"error": "Application not found"}), 404
    return jsonify({
        "id": row.id,
        "company": row.company,
        "position": row.position,
        "date": row.date.isoformat(),
        "match_summary": row.match_summary,
        "cv_path": row.cv_path,
        "cover_letter_path": row.cover_letter_path,
        "status": row.status,
    })
