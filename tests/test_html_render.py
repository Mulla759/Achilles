"""Unit tests for achilles.html_render. Pure, no network, no browser.

These pin down the two things that matter most for an HTML renderer that
feeds a headless-Chromium PDF service: (1) untrusted resume text can never
become live markup, and (2) the per-section entry geometry (which field lands
top-right vs. bottom-right) matches templates/typist.typ exactly, since that
.typ file is the layout's source of truth.
"""

from __future__ import annotations

from achilles.html_render import render_html
from achilles.models import Contact, Entry, Resume, SkillGroup


def _resume(**overrides) -> Resume:
    base = dict(contact=Contact(name="Jordan Rivera"))
    base.update(overrides)
    return Resume(**base)


# --------------------------------------------------------------------------
# Escaping
# --------------------------------------------------------------------------


def test_bullet_html_is_escaped_not_executed():
    payload = 'Cut cost by 5 & 10 < 20 > 15 "quoted" <script>alert(1)</script>'
    resume = _resume(
        experience=[Entry(role="Engineer", org="Acme", bullets=[payload])],
    )
    out = render_html(resume)

    # The raw dangerous substrings must never appear verbatim.
    assert "<script>alert(1)</script>" not in out
    assert "5 & 10" not in out
    assert "20 > 15" not in out

    # The escaped, inert forms must be present and visible as text.
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in out
    assert "5 &amp; 10" in out
    assert "20 &gt; 15" in out
    assert "&quot;quoted&quot;" in out


def test_escaping_covers_entry_fields_not_just_bullets():
    resume = _resume(
        projects=[Entry(role='<b>Name</b>', stack="A & B", date='2024"')],
    )
    out = render_html(resume)
    assert "<b>Name</b>" not in out
    assert "&lt;b&gt;Name&lt;/b&gt;" in out
    assert "A &amp; B" in out


# --------------------------------------------------------------------------
# Section skipping
# --------------------------------------------------------------------------


def test_empty_sections_are_skipped():
    resume = _resume(experience=[Entry(role="Engineer", org="Acme")])
    out = render_html(resume)
    assert ">Projects<" not in out
    assert ">Leadership &amp; Awards<" not in out
    assert ">Work Experience<" in out


# --------------------------------------------------------------------------
# Entry geometry per section
# --------------------------------------------------------------------------


def test_education_entry_puts_location_before_date():
    resume = _resume(
        education=[
            Entry(
                role="B.S. Computer Science",
                org="State University",
                date="Expected May 2027",
                location="Columbus, OH",
            )
        ],
    )
    out = render_html(resume)
    # Education: line1 = school | location (right); line2 = degree | date (right).
    assert out.index("Columbus, OH") < out.index("Expected May 2027")
    assert out.index("State University") < out.index("B.S. Computer Science")


def test_experience_entry_puts_date_before_location():
    """Date rides the first row and location the second, whichever way the
    left-hand slots are ordered — so both `lead_with` modes are asserted."""
    entry = Entry(
        role="Software Engineer Intern",
        org="Acme Corp",
        date="Jun 2026 - Aug 2026",
        location="Remote",
    )
    for lead_with in ("role", "org"):
        out = render_html(_resume(experience=[entry], lead_with=lead_with))
        assert out.index("Jun 2026 - Aug 2026") < out.index("Remote"), lead_with


def test_leadership_entry_geometry_matches_experience():
    # lead_with is set explicitly rather than relying on the model default, so
    # this test asserts the geometry rule and not whichever ordering happens to
    # be the current default.
    resume = _resume(
        lead_with="org",
        leadership=[
            Entry(role="President", org="Product Club", date="2025", location="Columbus, OH")
        ],
    )
    out = render_html(resume)
    # Date rides the first row, location the second — same as Work Experience.
    assert out.index("2025") < out.index("Columbus, OH")
    assert out.index("Product Club") < out.index("President")


def test_leadership_entry_geometry_default_leads_with_role():
    """The standard typist ordering: job title bold first, org italic beneath."""
    resume = _resume(
        leadership=[
            Entry(role="President", org="Product Club", date="2025", location="Columbus, OH")
        ],
    )
    out = render_html(resume)
    assert out.index("President") < out.index("Product Club")
    assert out.index("2025") < out.index("Columbus, OH")


def test_leadership_secondary_row_omitted_when_both_parts_empty():
    resume = _resume(
        lead_with="org",
        leadership=[Entry(role="", org="ColorStack Chair", date="2025", location="")],
    )
    out = render_html(resume)
    # role="" and location="" -> secondary row's left AND right are both empty,
    # so the whole second grid row must be omitted, not rendered blank.
    assert 'entry-row secondary' not in out


# --------------------------------------------------------------------------
# lead_with="role"
# --------------------------------------------------------------------------


def test_lead_with_role_swaps_only_the_left_slots():
    entry = Entry(role="Engineer", org="Acme Corp", date="Jan 2020", location="Remote")

    org_first = render_html(_resume(experience=[entry], lead_with="org"))
    role_first = render_html(_resume(experience=[entry], lead_with="role"))

    # Left-hand slots swap.
    assert org_first.index("Acme Corp") < org_first.index("Engineer")
    assert role_first.index("Engineer") < role_first.index("Acme Corp")

    # Right-hand slots (date then location) are unaffected by lead_with.
    assert org_first.index("Jan 2020") < org_first.index("Remote")
    assert role_first.index("Jan 2020") < role_first.index("Remote")


# --------------------------------------------------------------------------
# Projects
# --------------------------------------------------------------------------


def test_projects_render_single_line_with_stack_separator():
    resume = _resume(
        projects=[Entry(role="InsightBot", stack="Python, FAISS", date="2024")],
    )
    out = render_html(resume)
    assert "InsightBot | " in out or "InsightBot</span> | " in out
    assert out.index("InsightBot") < out.index("Python, FAISS") < out.index("2024")
    # Single line: no secondary/italic entry row for a project entry.
    assert 'entry-row secondary' not in out


def test_projects_omit_separator_when_stack_empty():
    resume = _resume(projects=[Entry(role="SoloApp", stack="", date="2023")])
    out = render_html(resume)
    assert "SoloApp" in out
    # No stack -> no " | " separator and no italic stack span at all.
    assert 'class="stack"' not in out


# --------------------------------------------------------------------------
# Custom section titles
# --------------------------------------------------------------------------


def test_custom_section_titles_are_honored():
    resume = _resume(
        education=[Entry(role="B.S.", org="State U")],
        education_title="Learning",
        experience=[Entry(role="Intern", org="Acme")],
        experience_title="Employment History",
    )
    out = render_html(resume)
    assert ">Learning<" in out
    assert ">Employment History<" in out
    assert ">Education<" not in out
    assert ">Work Experience<" not in out


# --------------------------------------------------------------------------
# Density
# --------------------------------------------------------------------------


def test_density_changes_css_and_shrinks_body_size():
    out_roomy = render_html(_resume(), density=0.0)
    out_tight = render_html(_resume(), density=1.0)

    assert out_roomy != out_tight
    assert "font-size: 9.8pt" in out_roomy
    assert "font-size: 8.6pt" in out_tight


# --------------------------------------------------------------------------
# Empty resume / document shape
# --------------------------------------------------------------------------


def test_empty_resume_does_not_raise_and_contains_name():
    resume = Resume(contact=Contact(name="Only Name"))
    out = render_html(resume)
    assert "Only Name" in out


def test_output_shape_doctype_and_single_style_block():
    out = render_html(_resume())
    assert out.startswith("<!DOCTYPE html>")
    assert out.count("<style>") == 1
    assert "</html>" in out
    assert "<script" not in out


def test_skills_section_renders_label_and_items():
    resume = _resume(skills=[SkillGroup(label="Languages", items="Python, SQL")])
    out = render_html(resume)
    assert "Languages" in out
    assert "Python, SQL" in out
