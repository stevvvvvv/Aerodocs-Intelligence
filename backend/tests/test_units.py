from app.analysis.contradictions import extract_quantities, numeric_conflict
from app.generation.citations import check_citations
from app.generation.extractive import extractive_answer
from app.generation.prompts import ABSTAIN_TOKEN
from app.ingestion.chunker import chunk_pages, is_heading, split_sections
from app.ingestion.pdf_extract import PageText, clean_pages
from app.retrieval.search import Hit


def hit(text, doc=1, family="F", version="A", current=True, section=None):
    return Hit(1, doc, "T", family, version, current, section, 1, 1, text, 0.5, 0.0, 0.0)


# --- Découpage ------------------------------------------------------------------
def test_heading_detection_easa_and_manuals():
    for h in ["M.A.301 Continuing airworthiness tasks", "AMC1 145.A.30(e) Personnel requirements",
              "CS 25.571 Damage-tolerance and fatigue evaluation of structure", "SUBPART C",
              "2.3 Servicing of the shock strut", "TORQUE VALUES"]:
        assert is_heading(h), h
    for not_h in ["1. The operator shall ensure that the aircraft is maintained in an airworthy condition.",
                  "MIL-PRF-5606.", "Charge the shock strut to 1,450 psi,", "20 °C with the strut extended"]:
        assert not is_heading(not_h), not_h


def test_running_headers_and_hyphenation_are_cleaned():
    raw = [f"ACME Manual\nThe main-\ntenance task {w}.\nPage {i} of 4" for i, w in enumerate(["one", "two", "three", "four"], 1)]
    cleaned = clean_pages(raw)
    assert all("ACME Manual" not in p and "Page" not in p for p in cleaned)
    assert "maintenance task one." in cleaned[0]


def test_chunks_keep_pages_and_do_not_cross_sections():
    pages = [
        PageText(1, "1 GENERAL\n" + "General text line about the strut.\n" * 10),
        PageText(2, "2 SERVICING\n" + "Servicing line with nitrogen at 1,450 psi.\n" * 40),
    ]
    chunks = chunk_pages(pages, chunk_size=500, overlap=100)
    assert chunks[0].section == "1 GENERAL" and chunks[0].page_end == 1
    assert all(c.section == "2 SERVICING" for c in chunks[1:])
    assert all(c.page_start == 2 for c in chunks[1:])
    assert all(len(c.text) <= 600 for c in chunks)


def test_split_sections():
    secs = split_sections([PageText(1, "1 GENERAL\nabc\n2 SERVICING\ndef"), PageText(2, "more def")])
    assert [s.title for s in secs] == ["1 GENERAL", "2 SERVICING"]
    assert "more def" in secs[1].text and secs[1].first_page == 1


# --- Citations ------------------------------------------------------------------
def test_citations_normalized_and_invalid_removed():
    c = check_citations("Interval is 500 FH [S1, S3]. Torque is 90 N.m [S9]. Pressure 1,450 psi [S2].", 3)
    assert c.cited == [1, 3, 2]
    assert c.invalid == [9]
    assert "[S1][S3]" in c.text and "[S9]" not in c.text
    assert round(c.coverage, 2) == 0.67  # la phrase sur le couple n'a plus de citation valide


def test_citation_coverage_full():
    assert check_citations("Value A is 3 mm [S1].\nValue B is 4 mm [S2].", 2).coverage == 1.0


# --- Extraction sans LLM -------------------------------------------------------------
def test_extractive_abstains_without_support():
    hits = [hit("Replace the EDP case drain filter element every 1,000 FH.")]
    assert extractive_answer("What is the nose wheel tire pressure?", hits) == ABSTAIN_TOKEN
    ans = extractive_answer("When is the case drain filter replaced?", hits)
    assert "1,000 FH" in ans and "[S1]" in ans


# --- Contradictions ------------------------------------------------------------------
def test_quantities_parsing():
    q = extract_quantities("Charge to 1,450 psi. Inspect every 500 FH or 6 months.")
    assert [(x.value, x.unit) for x in q] == [(1450, "psi"), (500, "FH"), (6, "mo")]


def test_numeric_conflict_same_context_only():
    a = hit("Inspect the dynamic seals for leakage every 500 FH.", doc=1)
    b = hit("Inspect the dynamic seals for leakage every 400 FH until the kit is installed.", doc=2)
    c = hit("Replace the case drain filter element every 1,000 FH.", doc=3)
    assert numeric_conflict(a, b) is not None
    assert numeric_conflict(a, c) is None


def test_repeated_body_sentence_is_not_mistaken_for_footer():
    raw = ["Intro\nRecord the task in the records.", "Other text\nRecord the task in the records.", "Last page text"]
    assert all("Record the task" in p for p in clean_pages(raw)[:2])


def test_diff_between_demo_revisions_has_no_false_changes(demo_pdfs):
    from app.ingestion.pdf_extract import extract_pdf
    from app.ingestion.chunker import split_sections

    a = {s.title: s.text for s in split_sections(extract_pdf(demo_pdfs["AMM-32-11_RevA.pdf"]))}
    b = {s.title: s.text for s in split_sections(extract_pdf(demo_pdfs["AMM-32-11_RevB.pdf"]))}
    assert a["2.1 Nitrogen charging of the shock strut"] == b["2.1 Nitrogen charging of the shock strut"]
    assert "Record the task" in a["3.2 Dynamic seal inspection"]
