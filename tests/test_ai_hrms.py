"""Automated Pytest Suite for AI HRMS Portal Services & Endpoints."""

from utils.ai_resume_parser import parse_resume, match_candidate_job
from utils.ai_helpdesk import process_helpdesk_query
from utils.ai_interview_evaluator import evaluate_interview_notes
from utils.ai_attrition_analytics import compute_attrition_and_burnout_analytics


def test_resume_parser_unit():
    raw_text = b"John Doe\nEmail: john@example.com\nPhone: (555) 123-4567\nSkills: Python, SQL, React, FastAPI, Docker\nExperience: 2019 to 2024 (5 years)"
    parsed = parse_resume(raw_text, filename="John_Doe_Resume.pdf")
    assert parsed["candidate_name"] is not None
    assert "john@example.com" in parsed["email"]
    assert "Python" in parsed["skills"]

    # Match candidate against Job Description
    jd = "Looking for a Python software developer with SQL and Docker experience."
    match = match_candidate_job(parsed, jd)
    assert match["match_score"] >= 60
    assert "Python" in match["matched_skills"] or "Sql" in match["matched_skills"]


def test_ai_helpdesk_query_and_fallback(db_engine, seed_employee):
    emp_id = seed_employee["employee_id"]

    # Normal policy query
    res = process_helpdesk_query(emp_id, "What is the paid leave policy?")
    assert res["answer"] is not None
    assert res["escalated"] is False

    # High complexity / escalation query
    res_esc = process_helpdesk_query(emp_id, "I have an urgent salary dispute and want to speak to a human manager")
    assert res_esc["escalated"] is True
    assert res_esc["ticket_id"] is not None


def test_interview_evaluator_unit():
    notes = "Candidate showed excellent technical skills in Python and SQL, clear communication, and impressive problem solving."
    eval_report = evaluate_interview_notes("Jane Smith", "Senior Developer", notes)
    
    assert eval_report["overall_rating"] >= 7.5
    assert "positive" in eval_report["sentiment_analysis"]
    assert eval_report["overall_recommendation"] in ("Hire", "Strong Hire")


def test_attrition_analytics_unit(db_engine):
    analytics = compute_attrition_and_burnout_analytics()
    assert "summary" in analytics
    assert "overall_turnover_index" in analytics["summary"]
    assert isinstance(analytics["all_employee_analytics"], list)


def test_ai_hrms_api_endpoints(client, seed_admin):
    with client.session_transaction() as sess:
        sess["admin_logged_in"] = True
        sess["admin_username"] = seed_admin["username"]
        sess["admin_role"] = "admin"

    # Test /api/ai/parse-resume
    res = client.post("/api/ai/parse-resume", data={"resume_text": "Alex Dev\nEmail: alex@dev.io\nSkills: Python, React"})
    assert res.status_code == 200
    assert res.get_json()["ok"] is True

    # Test /api/ai/screen-candidate
    res = client.post("/api/ai/screen-candidate", json={
        "resume_text": "Alex Dev\nEmail: alex@dev.io\nSkills: Python, React",
        "job_description": "Python Developer needed"
    })
    assert res.status_code == 200
    assert res.get_json()["match_result"]["match_score"] > 50

    # Test /api/ai/hr-helpdesk
    res = client.post("/api/ai/hr-helpdesk", json={"query": "How many sick days do I get?"})
    assert res.status_code == 200
    assert res.get_json()["data"]["answer"] is not None

    # Test /api/ai/evaluate-interview
    res = client.post("/api/ai/evaluate-interview", json={
        "candidate_name": "Alex Dev",
        "position": "Python Engineer",
        "notes": "Great technical skills and clear communication."
    })
    assert res.status_code == 200
    assert res.get_json()["evaluation"]["overall_rating"] >= 7.0

    # Test /api/ai/attrition-analytics
    res = client.get("/api/ai/attrition-analytics")
    assert res.status_code == 200
    assert res.get_json()["ok"] is True
