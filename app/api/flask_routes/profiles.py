"""Profile routes for the Flask app."""

from flask import Blueprint, jsonify, request
from app.models.schemas import CandidateProfile
from app.services.profile_manager import load_profile, save_profile

profiles_bp = Blueprint("profiles", __name__, url_prefix="/profiles")


@profiles_bp.get("/")
def list_profiles():
    return jsonify(load_profile().model_dump(mode="json"))


@profiles_bp.get("/<profile_id>")
def get_profile(profile_id):
    del profile_id
    return jsonify(load_profile().model_dump(mode="json"))


@profiles_bp.post("/")
def save_profile_route():
    payload = request.get_json(silent=True) or {}
    profile = CandidateProfile.model_validate(payload)
    save_profile(profile)
    return jsonify(profile.model_dump(mode="json"))
