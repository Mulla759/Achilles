from __future__ import annotations

from achilles.models import Contact, Entry, Resume
from achilles.rubric import grade

CONTACT = Contact(name="Jane Doe", email="jane.doe@example.com")


def _resume(education=None, experience=None) -> Resume:
    return Resume(
        contact=CONTACT,
        education=education or [],
        experience=experience or [],
    )


def _gate(report, name):
    return next(g for g in report.gates if g.name == name)


# --------------------------------------------------------------------------
# graduation
# --------------------------------------------------------------------------


def test_graduation_passes_with_degree_and_year():
    edu = [Entry(role="B.S. Computer Science", org="State University", date="Expected May 2026")]
    r = grade(_resume(education=edu), text="x" * 250, pages=1)
    g = _gate(r, "graduation")
    assert g.passed is True
    assert g.score == 100


def test_graduation_fails_with_no_education():
    r = grade(_resume(), text="x" * 250, pages=1)
    g = _gate(r, "graduation")
    assert g.passed is False
    assert g.score == 0


def test_graduation_fails_when_date_has_no_year():
    edu = [Entry(role="B.S. Computer Science", org="State University", date="Expected soon")]
    r = grade(_resume(education=edu), text="x" * 250, pages=1)
    g = _gate(r, "graduation")
    assert g.passed is False
    assert "graduation year" in g.offenders[0]


def test_graduation_fails_when_role_has_no_degree_title():
    edu = [Entry(role="Teaching Assistant", org="State University", date="2026")]
    r = grade(_resume(education=edu), text="x" * 250, pages=1)
    g = _gate(r, "graduation")
    assert g.passed is False
    assert "degree title" in g.offenders[0]


# --------------------------------------------------------------------------
# semantics
# --------------------------------------------------------------------------

GOOD_BULLET = "Led weekly product syncs across 3 cross-functional teams, cutting release delays by 40%."
WEAK_BULLET = "Responsible for helping the team with various onboarding tasks and documentation."


def test_semantics_passes_when_all_bullets_open_strong():
    exp = [Entry(role="PM Intern", bullets=[GOOD_BULLET, "Built an internal tool used by 40 engineers."])]
    r = grade(_resume(experience=exp), text="x" * 250, pages=1)
    g = _gate(r, "semantics")
    assert g.passed is True
    assert g.score == 100


def test_semantics_fails_with_weak_opener():
    exp = [Entry(role="PM Intern", bullets=[GOOD_BULLET, WEAK_BULLET])]
    r = grade(_resume(experience=exp), text="x" * 250, pages=1)
    g = _gate(r, "semantics")
    assert g.passed is False
    assert g.score == 50
    assert any("Responsible for" in o for o in g.offenders)


def test_semantics_empty_bullets_is_safe_failing_gate():
    r = grade(_resume(experience=[Entry(role="PM Intern", bullets=[])]), text="x" * 250, pages=1)
    g = _gate(r, "semantics")
    assert g.passed is False
    assert g.score == 0


# --------------------------------------------------------------------------
# metrics
# --------------------------------------------------------------------------


def test_metrics_passes_when_majority_of_bullets_have_numbers():
    exp = [Entry(role="PM Intern", bullets=[
        GOOD_BULLET,
        "Built an internal tool used by 40 engineers.",
        "Mentored new hires on team norms.",
    ])]
    r = grade(_resume(experience=exp), text="x" * 250, pages=1)
    g = _gate(r, "metrics")
    assert g.passed is True  # 2/3 = 67% >= 60
    assert g.score == 67


def test_metrics_fails_when_no_bullets_have_numbers():
    exp = [Entry(role="PM Intern", bullets=[WEAK_BULLET, "Mentored new hires on team norms."])]
    r = grade(_resume(experience=exp), text="x" * 250, pages=1)
    g = _gate(r, "metrics")
    assert g.passed is False
    assert g.score == 0


def test_metrics_catches_sample_formats_from_spec():
    exp = [Entry(role="PM Intern", bullets=[
        "Drove adoption to ~95% across the team.",
        "Cut latency 1.4K+ requests per minute.",
        "Scaled the pilot to 300+ users.",
        "Reduced sync time from sub-2s to sub-1s.",
        "Migrated onboarding from 2 days -> under 1 hr.",
        "Grew the waitlist by 50+ signups.",
    ])]
    r = grade(_resume(experience=exp), text="x" * 250, pages=1)
    g = _gate(r, "metrics")
    assert g.score == 100


# --------------------------------------------------------------------------
# storyline
# --------------------------------------------------------------------------


def test_storyline_passes_with_action_object_outcome_bullets():
    exp = [Entry(role="PM Intern", bullets=[GOOD_BULLET, "Built a dashboard, enabling faster triage."])]
    r = grade(_resume(experience=exp), text="x" * 250, pages=1)
    g = _gate(r, "storyline")
    assert g.passed is True


def test_storyline_fails_on_duty_list_bullets():
    exp = [Entry(role="PM Intern", bullets=[
        "Led a small team of interns.",  # strong verb, no metric/connective -> fails
        WEAK_BULLET,
    ])]
    r = grade(_resume(experience=exp), text="x" * 250, pages=1)
    g = _gate(r, "storyline")
    assert g.passed is False
    assert g.score == 0


# --------------------------------------------------------------------------
# one_page
# --------------------------------------------------------------------------


def test_one_page_passes_at_exactly_one():
    r = grade(_resume(), text="x" * 250, pages=1)
    g = _gate(r, "one_page")
    assert g.passed is True
    assert g.score == 100


def test_one_page_fails_and_reports_count():
    r = grade(_resume(), text="x" * 250, pages=2)
    g = _gate(r, "one_page")
    assert g.passed is False
    assert g.score == 0
    assert "2 pages" in g.detail


# --------------------------------------------------------------------------
# mac (Metric + Action + Context) — the gate the user cares most about
# --------------------------------------------------------------------------


def test_mac_passes_when_all_three_limbs_present():
    exp = [Entry(role="PM Intern", bullets=[GOOD_BULLET])]
    r = grade(_resume(experience=exp), text="x" * 250, pages=1)
    g = _gate(r, "mac")
    assert g.passed is True
    assert g.score == 100
    assert g.offenders == []


def test_mac_offender_message_flags_only_the_missing_limb():
    # Strong verb (Action) + capitalized org name (Context), but no number (Metric).
    bullet = "Led weekly workshops for the Robotics Club at UMN."
    exp = [Entry(role="Club Lead", bullets=[bullet])]
    r = grade(_resume(experience=exp), text="x" * 250, pages=1)
    g = _gate(r, "mac")
    assert g.passed is False
    assert len(g.offenders) == 1
    assert g.offenders[0] == f"MISSING metric — {bullet}"


def test_mac_offender_lists_multiple_missing_limbs():
    r = grade(_resume(experience=[Entry(role="PM Intern", bullets=[WEAK_BULLET])]), text="x" * 250, pages=1)
    g = _gate(r, "mac")
    assert g.passed is False
    assert "MISSING metric, action, context" in g.offenders[0]


def test_mac_empty_bullets_is_safe_failing_gate():
    r = grade(_resume(experience=[Entry(role="PM Intern", bullets=[])]), text="x" * 250, pages=1)
    g = _gate(r, "mac")
    assert g.passed is False
    assert g.score == 0


# --------------------------------------------------------------------------
# ats_parseable
# --------------------------------------------------------------------------

PASS_TEXT = (
    "JANE DOE\n"
    "jane.doe@example.com | (555) 123-4567\n\n"
    "EDUCATION\n"
    "B.S. Computer Science, State University, Expected May 2026\n\n"
    "EXPERIENCE\n"
    "Software Engineering Intern, Example Corp, Summer 2025\n"
    "- Built an internal tool used by 40 engineers, cutting review time by 25%.\n"
    "- Led a migration from a legacy service to a new API, resolving 15 open bugs.\n"
)


def test_ats_parseable_passes_clean_single_column_resume():
    assert len(PASS_TEXT) > 200
    r = grade(_resume(), text=PASS_TEXT, pages=1)
    g = _gate(r, "ats_parseable")
    assert g.passed is True
    assert g.score == 100
    assert g.offenders == []


def test_ats_parseable_fails_short_image_like_text():
    r = grade(_resume(), text="Jane Doe\nSoftware Engineer", pages=1)
    g = _gate(r, "ats_parseable")
    assert g.passed is False
    assert any("image-based" in o for o in g.offenders)
    assert any("header" in o for o in g.offenders)


def test_ats_parseable_fails_on_table_like_layout():
    lines = ["EDUCATION", "EXPERIENCE", "jane.doe@example.com"]
    lines += ["Col1      Col2      Col3      Col4" for _ in range(10)]
    text = "\n".join(lines)
    assert len(text) > 200
    r = grade(_resume(), text=text, pages=1)
    g = _gate(r, "ats_parseable")
    assert g.passed is False
    assert any("table" in o for o in g.offenders)


def test_ats_parseable_fails_on_missing_email():
    text = ("EDUCATION\nB.S. Computer Science\n\nEXPERIENCE\n" + ("Did engineering work. " * 20))
    assert len(text) > 200
    no_email_resume = Resume(contact=Contact(name="Jane Doe"))  # no email on contact either
    r = grade(no_email_resume, text=text, pages=1)
    g = _gate(r, "ats_parseable")
    assert g.passed is False
    assert any("email" in o for o in g.offenders)


# --------------------------------------------------------------------------
# empty-input safety
# --------------------------------------------------------------------------


def test_grade_on_fully_empty_resume_never_raises():
    empty = Resume(contact=Contact(name="Nobody"))
    r = grade(empty, text="", pages=0)
    assert r.passed is False
    for g in r.gates:
        assert g.passed is False
        assert g.detail  # every gate must populate a human-readable detail


def test_grade_gate_count_and_names():
    r = grade(_resume(), text=PASS_TEXT, pages=1)
    names = [g.name for g in r.gates]
    assert names == [
        "graduation", "semantics", "metrics", "storyline", "one_page", "mac", "ats_parseable",
    ]
