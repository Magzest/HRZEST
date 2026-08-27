# -*- coding: utf-8 -*-
"""Blueprint for AI-powered HRMS features (Recruitment, Helpdesk, Interview Evaluation, Attrition Analytics)."""

from flask import Blueprint, request, jsonify, render_template, session
from utils.ai_resume_parser import parse_resume, match_candidate_job
from utils.ai_helpdesk import process_helpdesk_query
from utils.ai_interview_evaluator import evaluate_interview_notes
from utils.ai_attrition_analytics import compute_attrition_and_burnout_analytics
from utils.auth import admin_required, _hash_token
from utils.helpers import _db

ai_hrms_bp = Blueprint("ai_hrms", __name__)


def _resolve_bearer_identity():
    """Bearer-token counterpart of the session.get(...) check below -- the
    helpdesk is usable by both employees and admins (no single
    api_required/employee_api_required decorator covers both personas), so
    this looks the token up against api_tokens directly for either type.
    Mobile has no Flask session cookie at all, so without this every mobile
    helpdesk request silently fell through to the client's canned
    error-fallback text instead of a real AI answer.
    """
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token_hash = _hash_token(auth[7:])
    with _db() as (cursor, _conn):
        cursor.execute(
            "SELECT identity FROM api_tokens WHERE token=%s AND token_type IN ('employee','admin') AND expires_at > NOW()",
            (token_hash,)
        )
        row = cursor.fetchone()
    return row[0] if row else None


@ai_hrms_bp.route("/recruitment")
@admin_required
def recruitment_page():
    """Render the AI-Powered Recruitment & Candidate Screening Portal."""
    return render_template("recruitment.html")


@ai_hrms_bp.route("/api/ai/parse-resume", methods=["POST"])
@admin_required
def api_parse_resume():
    """API Endpoint: Parse uploaded resume document or raw text."""
    file = request.files.get("resume_file")
    if file:
        content = file.read()
        parsed = parse_resume(content, filename=file.filename)
    else:
        raw_text = request.form.get("resume_text") or (request.get_json(silent=True) or {}).get("resume_text", "")
        if not raw_text:
            return jsonify({"ok": False, "msg": "No resume file or text provided."}), 400
        parsed = parse_resume(raw_text.encode("utf-8"), filename="Resume.txt")
        
    return jsonify({"ok": True, "parsed_profile": parsed})


@ai_hrms_bp.route("/api/ai/screen-candidate", methods=["POST"])
@admin_required
def api_screen_candidate():
    """API Endpoint: Score and match parsed candidate profile against job description."""
    data = request.get_json(silent=True) or {}
    parsed_candidate = data.get("parsed_profile")
    job_description = data.get("job_description", "")
    
    if not parsed_candidate:
        # Fallback if raw resume_text was passed
        resume_text = data.get("resume_text", "")
        if resume_text:
            parsed_candidate = parse_resume(resume_text.encode("utf-8"))
        else:
            return jsonify({"ok": False, "msg": "Candidate profile or resume text required."}), 400

    match_result = match_candidate_job(parsed_candidate, job_description)
    return jsonify({
        "ok": True,
        "parsed_profile": parsed_candidate,
        "match_result": match_result,
    })


@ai_hrms_bp.route("/api/ai/hr-helpdesk", methods=["POST"])
def api_hr_helpdesk():
    """API Endpoint: Conversational HR Helpdesk Q&A with automatic ticket escalation."""
    emp_id = session.get("employee_id") or session.get("admin_username") or _resolve_bearer_identity()
    if not emp_id:
        return jsonify({"ok": False, "msg": "Login required."}), 401

    data = request.get_json(silent=True) or {}
    query = (data.get("query") or data.get("message") or "").strip()

    if not query:
        return jsonify({"ok": False, "msg": "Query text required."}), 400

    result = process_helpdesk_query(emp_id, query)
    return jsonify({"ok": True, "data": result})


@ai_hrms_bp.route("/api/ai/evaluate-interview", methods=["POST"])
@admin_required
def api_evaluate_interview():
    """API Endpoint: Synthesize interviewer notes into structured scorecard & sentiment analysis."""
    data = request.get_json(silent=True) or {}
    candidate_name = data.get("candidate_name", "Candidate")
    position = data.get("position", "Software Engineer")
    notes = data.get("notes", "")
    
    if not notes:
        return jsonify({"ok": False, "msg": "Interviewer notes required."}), 400

    evaluation = evaluate_interview_notes(candidate_name, position, notes)
    return jsonify({"ok": True, "evaluation": evaluation})


@ai_hrms_bp.route("/api/ai/attrition-analytics")
@admin_required
def api_attrition_analytics():
    """API Endpoint: Predict turnover trends and burnout risk indicators."""
    active_cid = session.get("active_company_id")
    analytics = compute_attrition_and_burnout_analytics(company_id=active_cid)
    return jsonify({"ok": True, "analytics": analytics})
