from __future__ import annotations

from achilles.keywords import coverage_forms, extract
from achilles.models import Keyword
from achilles.scan import scan, scan_pdf_text

# --------------------------------------------------------------------------
# scan(): whitespace-collapse matching — the original prototype's key insight
# --------------------------------------------------------------------------


def test_scan_matches_term_split_across_a_line_break():
    # "cross functional" wrapped by the PDF renderer's line break — the extracted
    # text has a newline where a space would be, and normalize() must treat them
    # the same way a real ATS parser's text stream does.
    text = "Worked cross\nfunctional teams to ship the feature."
    kw = [Keyword(label="Cross-functional", forms=["cross functional"], required=True, group="soft")]
    report = scan(text, kw)
    assert report.hits[0].hit is True
    assert report.hits[0].matched_form == "cross functional"


def test_scan_matches_multiword_term_split_by_newline():
    text = "Built dashboards using Power\nBI for weekly reporting."
    kw = [Keyword(label="Power BI", forms=["power bi"], required=False, group="data")]
    report = scan(text, kw)
    assert report.hits[0].hit is True


def test_scan_is_case_insensitive():
    text = "Proficient in SQL and Python."
    kw = [Keyword(label="SQL", forms=["sql"], required=True, group="data")]
    report = scan(text, kw)
    assert report.hits[0].hit is True


def test_scan_no_match_when_form_absent():
    text = "Built a React app."
    kw = [Keyword(label="Kubernetes", forms=["kubernetes", "k8s"], required=True, group="engineering")]
    report = scan(text, kw)
    assert report.hits[0].hit is False
    assert report.hits[0].matched_form == ""


def test_scan_uses_first_matching_form():
    # "a/b test" is a substring of the text's "a/b tests", so it matches even
    # though it's listed before the more specific plural form — first-in-list
    # substring match wins, which is scan()'s documented behavior.
    text = "Shipped several a/b tests."
    kw = [Keyword(label="A/B testing", forms=["a/b testing", "a/b test", "a/b tests"], required=True, group="product")]
    report = scan(text, kw)
    assert report.hits[0].hit is True
    assert report.hits[0].matched_form == "a/b test"


def test_scan_word_count():
    report = scan("one two three", [])
    assert report.word_count == 3


def test_scan_empty_text_is_safe():
    report = scan("", [Keyword(label="SQL", forms=["sql"], required=True, group="data")])
    assert report.hits[0].hit is False
    assert report.word_count == 0
    assert report.total == 1
    assert report.matched == 0


def test_scan_empty_keywords_scores_100():
    report = scan("some resume text", [])
    assert report.total == 0
    assert report.score == 100
    assert report.required_score == 100


def test_scan_pdf_text_strips_form_feed_page_breaks():
    # A term straddling a page break would otherwise get glued to the next
    # page's first word once whitespace collapses; the form-feed must become
    # a real separator, not vanish.
    text = "Led cross\x0cfunctional planning."
    kw = [Keyword(label="Cross-functional", forms=["cross functional"], required=True, group="soft")]
    report = scan_pdf_text(text, kw)
    assert report.hits[0].hit is True


# --------------------------------------------------------------------------
# keywords.extract(): required-vs-preferred region detection
# --------------------------------------------------------------------------


def test_extract_marks_term_in_required_section_as_required():
    jd = """
    About the role: build data products.

    Required Qualifications:
    - Proficiency in SQL and Python
    - Experience with Tableau

    Preferred Qualifications:
    - Familiarity with Docker
    """
    kws = extract(jd)
    by_label = {k.label: k for k in kws}
    assert by_label["SQL"].required is True
    assert by_label["Python"].required is True
    assert by_label["Docker"].required is False


def test_extract_defaults_to_required_when_no_headings_present():
    jd = "We use React and TypeScript every day to build our product."
    kws = extract(jd)
    by_label = {k.label: k for k in kws}
    assert by_label["React"].required is True
    assert by_label["TypeScript"].required is True


def test_extract_only_emits_keywords_actually_present_in_jd():
    jd = "We are hiring a PM. Experience with SQL is a must."
    kws = extract(jd)
    labels = {k.label for k in kws}
    assert "SQL" in labels
    assert "Kubernetes" not in labels
    assert "React" not in labels


def test_extract_empty_jd_returns_empty_list():
    assert extract("") == []
    assert extract("   \n  ") == []


def test_extract_matches_term_split_across_lines_too():
    jd = "Minimum Qualifications:\nExperience with A/B\ntesting required."
    kws = extract(jd)
    labels = {k.label for k in kws}
    assert "A/B testing" in labels


def test_coverage_forms_known_and_unknown_label():
    assert "sql" in coverage_forms("SQL")
    assert coverage_forms("Not A Real Label") == []


def test_extract_fallback_other_group_from_skills_list_line():
    jd = "Tech stack: Snowflake, Figma, Salesforce, Notion, Airtable."
    kws = extract(jd)
    other = [k for k in kws if k.group == "other"]
    other_labels = {k.label for k in other}
    # Salesforce/Notion/Airtable aren't in the curated ontology, so they should
    # surface via the conservative comma-list fallback; Snowflake and Figma
    # ARE curated (data warehousing / wireframing) so shouldn't double up here.
    assert "Salesforce" in other_labels
    assert "Notion" in other_labels
    assert not any(k.label == "Snowflake" for k in other)


def test_extract_fallback_does_not_fire_on_ordinary_sentences():
    jd = (
        "We are a fast-growing company that values collaboration, honesty, "
        "and hard work above all else in every single thing that we do."
    )
    kws = extract(jd)
    assert not [k for k in kws if k.group == "other"]
