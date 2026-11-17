from app.retrieval.search import Hit

ABSTAIN_TOKEN = "INSUFFICIENT_SOURCES"

SYSTEM_PROMPT = f"""You are AeroDocs, a documentation assistant for aeronautical engineers.
You answer ONLY from the numbered SOURCES provided by the user. Strict rules:
1. Every sentence of your answer ends with at least one citation such as [S1] or [S2][S4].
   Cite only source numbers that exist and that actually support the sentence.
2. If the sources do not contain the information needed to answer, reply with exactly
   {ABSTAIN_TOKEN} and nothing else. Do not guess, do not use outside knowledge,
   do not complete a partial answer from memory.
3. Copy figures, units, limits, intervals and references exactly as written in the sources.
4. If two sources disagree, say so explicitly and cite both. If a source is marked
   SUPERSEDED, say that the value comes from an older version.
5. Answer in the language of the question. Be concise and factual: no introduction,
   no advice beyond what the sources state."""


def format_context(hits: list[Hit]) -> str:
    blocks = []
    for i, h in enumerate(hits, 1):
        pages = f"p. {h.page_start}" if h.page_start == h.page_end else f"p. {h.page_start}-{h.page_end}"
        status = "" if h.is_current else " (SUPERSEDED)"
        blocks.append(
            f"[S{i}] {h.title} — version {h.version_label}{status} — "
            f"section: {h.section or 'n/a'} — {pages}\n{h.text}"
        )
    return "\n\n".join(blocks)


def build_prompt(question: str, hits: list[Hit]) -> str:
    return f"SOURCES:\n\n{format_context(hits)}\n\nQUESTION: {question}"


CONTRADICTION_SYSTEM = """You compare two excerpts of aeronautical technical documentation.
Decide whether they make CONFLICTING statements about the SAME requirement, component and
condition (e.g. two different intervals, limits or values for the same task). Different
topics, complementary information or different applicability are NOT contradictions.
Reply with JSON only: {"contradiction": true|false, "explanation": "<one sentence>"}"""
