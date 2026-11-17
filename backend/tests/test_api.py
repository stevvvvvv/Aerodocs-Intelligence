"""Tests de bout en bout via l'API, sur le corpus démo et un vrai PostgreSQL/pgvector."""
import app.generation.rag as rag
from scripts.make_demo_pdfs import MANIFEST
from tests.conftest import upload

SEAL_Q = "What is the inspection interval for the shock strut dynamic seals?"


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["embeddings"] == "hashing"


def test_upload_validation(client, seeded, demo_pdfs):
    r = upload(client, demo_pdfs["SB-32-014.pdf"], MANIFEST[2])
    assert r.status_code == 409  # même fichier (sha256) déjà importé
    r = client.post("/api/documents", files={"file": ("x.pdf", b"hello", "application/pdf")},
                    data={"family": "x", "version_label": "1"})
    assert r.status_code == 415


def test_only_latest_revision_is_current(client, seeded):
    docs = {(d["family"], d["version_label"]): d for d in client.get("/api/documents").json()}
    assert docs[("AMM 32-11 MLG Shock Strut", "Rev. B")]["is_current"]
    assert not docs[("AMM 32-11 MLG Shock Strut", "Rev. A")]["is_current"]


def test_answer_has_precise_citations(client, seeded):
    out = client.post("/api/query", json={"question": "What is the torque value for the shock strut gland nut?"}).json()
    assert out["status"] == "answered"
    assert "90 N.m" in out["answer"] and "85 N.m" not in out["answer"]  # Rev. A (85 N.m) est remplacée
    cited = [s for s in out["sources"] if s["cited"]]
    assert cited and all(s["is_current"] for s in cited)
    assert all(s["page_start"] >= 1 and s["version_label"] for s in cited)


def test_refuses_when_sources_insufficient(client, seeded):
    for q in ["What is the nose wheel tire pressure?", "What is the torque value for the wheel axle nut?"]:
        out = client.post("/api/query", json={"question": q}).json()
        assert out["status"] == "refused", (q, out["answer"])
        assert out["answer"] is None and out["refusal_message"]


def test_contradiction_between_manual_and_service_bulletin(client, seeded):
    out = client.post("/api/query", json={"question": SEAL_Q}).json()
    assert out["status"] == "answered"
    kinds = {c["kind"] for c in out["contradictions"]}
    assert "numeric" in kinds


def test_superseded_versions_on_demand(client, seeded):
    out = client.post("/api/query", json={"question": SEAL_Q, "include_superseded": True}).json()
    assert any(not s["is_current"] for s in out["sources"])
    assert any(c["kind"] == "version_change" for c in out["contradictions"])
    assert out["warnings"]


def test_version_diff(client, seeded):
    a, b = seeded["AMM-32-11_RevA.pdf"]["id"], seeded["AMM-32-11_RevB.pdf"]["id"]
    diff = client.get("/api/versions/diff", params={"from_id": a, "to_id": b}).json()
    changes = {c["section"]: c for c in diff["changes"]}
    assert changes["3.3 Lower bearing corrosion inspection"]["change"] == "added"
    seal = changes["3.2 Dynamic seal inspection"]
    assert seal["change"] == "modified"
    assert any("600 FH" in l and l.startswith("-") for l in seal["diff"])
    assert any("500 FH" in l and l.startswith("+") for l in seal["diff"])
    assert diff["unchanged_sections"] >= 2


def test_page_and_file_endpoints(client, seeded):
    doc_id = seeded["SB-32-014.pdf"]["id"]
    assert "32-1175-02" in client.get(f"/api/documents/{doc_id}/pages/1").json()["text"]
    r = client.get(f"/api/documents/{doc_id}/file")
    assert r.status_code == 200 and r.content.startswith(b"%PDF")


def test_audit_log(client, seeded):
    client.post("/api/query", json={"question": SEAL_Q})
    logs = client.get("/api/queries").json()
    assert logs and logs[0]["question"] == SEAL_Q and logs[0]["cited_chunk_ids"]


# --- Garde-fous post-génération, avec un LLM simulé -----------------------------------
class FakeLLM:
    name = "fake"

    def __init__(self, reply):
        self.reply = reply

    def generate(self, system, prompt, max_tokens=800):
        if "EXCERPT A" in prompt:
            return '{"contradiction": false, "explanation": "n/a"}'
        return self.reply


def test_hallucinated_citations_are_blocked(client, seeded, monkeypatch):
    monkeypatch.setattr(rag, "get_llm", lambda: FakeLLM("The interval is 750 FH [S12]. It is mandatory."))
    out = client.post("/api/query", json={"question": SEAL_Q}).json()
    assert out["status"] == "refused" and out["refusal_reason"] == "unsupported_answer"


def test_llm_abstention_is_respected(client, seeded, monkeypatch):
    monkeypatch.setattr(rag, "get_llm", lambda: FakeLLM("INSUFFICIENT_SOURCES"))
    out = client.post("/api/query", json={"question": SEAL_Q}).json()
    assert out["refusal_reason"] == "llm_abstained"


def test_valid_llm_answer_passes(client, seeded, monkeypatch):
    monkeypatch.setattr(rag, "get_llm", lambda: FakeLLM(
        "AMM 32-11 Rev. B requires a dynamic seal inspection every 500 FH [S1]. "
        "SB 32-014 requires 400 FH until the new seal kit is installed [S2]."))
    out = client.post("/api/query", json={"question": SEAL_Q}).json()
    assert out["status"] == "answered" and out["citation_coverage"] == 1.0


def test_delete_promotes_previous_revision(client, seeded):
    rev_b = seeded["AMM-32-11_RevB.pdf"]["id"]
    assert client.delete(f"/api/documents/{rev_b}").status_code == 204
    docs = {d["version_label"]: d for d in client.get("/api/documents").json() if d["family"].startswith("AMM 32-11")}
    assert "Rev. B" not in docs and docs["Rev. A"]["is_current"]


def test_read_only_mode_blocks_writes(client, seeded, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "read_only", True)
    assert client.delete(f"/api/documents/{seeded['SB-32-014.pdf']['id']}").status_code == 403
    r = client.post("/api/documents", files={"file": ("x.pdf", b"%PDF-1.4", "application/pdf")},
                    data={"family": "x", "version_label": "1"})
    assert r.status_code == 403
    assert client.get("/api/health").json()["read_only"] is True
