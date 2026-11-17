import { useEffect, useRef, useState } from "react";
import { STATIC_MODE, api } from "../api";
import { IconAlert, IconCheck, IconSend, IconX } from "../icons";
import type { Answer, Family, Source } from "../types";
import { SourceDrawer, pagesLabel } from "./SourceDrawer";

const EXAMPLES = [
  "What is the inspection interval for the shock strut dynamic seals?",
  "What is the torque value for the shock strut gland nut?",
  "What is the torque value for the wheel axle nut?",
  "How often should hydraulic fluid samples be taken?",
];

const KIND: Record<string, string> = {
  numeric: "Valeurs divergentes entre documents",
  llm: "Contradiction confirmée",
  version_change: "Évolution entre versions",
};

interface Turn {
  id: number;
  question: string;
  answer?: Answer;
  error?: string;
}

type StepState = "ok" | "fail" | "warn" | "skip";

function pipeline(a: Answer): { label: string; detail: string; state: StepState }[] {
  const r = a.refusal_reason;
  const gen = a.llm_provider === "extractive" ? "extraction" : a.llm_provider;
  return [
    { label: "Recherche hybride", detail: `${a.sources.length} passages`, state: "ok" },
    {
      label: "Pertinence",
      detail: a.top_similarity !== null ? `sim. max ${a.top_similarity.toFixed(2)}` : "aucun passage",
      state: r === "no_relevant_sources" ? "fail" : "ok",
    },
    {
      label: "Génération",
      detail: r === "llm_abstained" ? "abstention" : r === "llm_error" ? "indisponible" : gen,
      state: r === "no_relevant_sources" ? "skip" : r === "llm_abstained" || r === "llm_error" ? "fail" : "ok",
    },
    {
      label: "Citations vérifiées",
      detail: a.citation_coverage !== null ? `${Math.round(a.citation_coverage * 100)} % des phrases` : "—",
      state:
        r === "unsupported_answer"
          ? "fail"
          : a.status !== "answered"
            ? "skip"
            : (a.citation_coverage ?? 1) < 1
              ? "warn"
              : "ok",
    },
  ];
}

function Pipeline({ answer }: { answer: Answer }) {
  return (
    <ol className="pipeline">
      {pipeline(answer).map((s) => (
        <li key={s.label} className={s.state}>
          <span className="dot">
            {s.state === "ok" ? <IconCheck width={12} height={12} /> : s.state === "fail" ? <IconX width={12} height={12} /> : s.state === "warn" ? "!" : ""}
          </span>
          <span className="step-label">{s.label}</span>
          <span className="step-detail">{s.detail}</span>
        </li>
      ))}
    </ol>
  );
}

function AnswerText({ text, sources, onOpen }: { text: string; sources: Source[]; onOpen: (s: Source) => void }) {
  return (
    <div className="answer-text">
      {text.split(/(\[S\d+\])/g).map((p, i) => {
        const m = p.match(/^\[(S\d+)\]$/);
        const src = m && sources.find((s) => s.ref === m[1]);
        return src ? (
          <button key={i} className="cite" onClick={() => onOpen(src)} title={`${src.title} · ${pagesLabel(src)}`}>
            {src.ref}
          </button>
        ) : (
          <span key={i}>{p}</span>
        );
      })}
    </div>
  );
}

function SourceCard({ s, onOpen }: { s: Source; onOpen: (s: Source) => void }) {
  return (
    <button className={`source-card ${s.cited ? "cited" : ""}`} onClick={() => onOpen(s)}>
      <div className="source-top">
        <span className="ref-badge">{s.ref}</span>
        <span className="mono muted">{pagesLabel(s)}</span>
      </div>
      <div className="source-title">{s.title}</div>
      <div className="source-sub">
        {s.version_label}
        {!s.is_current && <span className="pill muted-pill">remplacée</span>}
        {s.cited && <span className="pill ok-pill">citée</span>}
      </div>
      <div className="sim">
        <div style={{ width: `${Math.max(4, Math.min(100, s.similarity * 100))}%` }} />
      </div>
    </button>
  );
}

function TurnView({ turn, onOpen }: { turn: Turn; onOpen: (s: Source) => void }) {
  const a = turn.answer;
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (a || turn.error) return;
    const t0 = Date.now();
    const id = window.setInterval(() => setElapsed(Math.floor((Date.now() - t0) / 1000)), 500);
    return () => window.clearInterval(id);
  }, [a, turn.error]);

  return (
    <section className="turn">
      <div className="question">{turn.question}</div>

      {!a && !turn.error && (
        <div className="card thinking">
          <div className="loader" />
          <div>
            <strong>Analyse en cours · {elapsed} s</strong>
            <p className="muted">Recherche, contrôle de pertinence, génération puis vérification des citations.</p>
            {elapsed > 15 && <p className="muted small">Un modèle local sur CPU peut prendre plus d'une minute.</p>}
          </div>
        </div>
      )}

      {turn.error && <div className="card error-card">{turn.error}</div>}

      {a && (
        <div className={`card answer ${a.status}`}>
          <div className="answer-head">
            <span className={`status ${a.status}`}>
              {a.status === "answered" ? <IconCheck width={14} height={14} /> : <IconX width={14} height={14} />}
              {a.status === "answered" ? "Réponse sourcée" : "Réponse refusée"}
            </span>
            <span className="mono muted small">
              {a.latency_ms < 1000 ? `${a.latency_ms} ms` : `${(a.latency_ms / 1000).toFixed(a.latency_ms < 10000 ? 1 : 0)} s`}
            </span>
          </div>

          <Pipeline answer={a} />

          {a.status === "answered" && a.answer ? (
            <AnswerText text={a.answer} sources={a.sources} onOpen={onOpen} />
          ) : (
            <p className="refusal">{a.refusal_message}</p>
          )}

          {a.contradictions.map((c, i) => {
            const sa = a.sources.find((s) => s.ref === c.ref_a);
            const sb = a.sources.find((s) => s.ref === c.ref_b);
            return (
              <div key={i} className={`callout ${c.kind}`}>
                <IconAlert />
                <div>
                  <strong>{KIND[c.kind]}</strong>
                  <span className="muted small"> · confiance {c.confidence}</span>
                  <p>{c.explanation}</p>
                  <div className="callout-refs">
                    {sa && <button className="cite" onClick={() => onOpen(sa)}>{sa.ref}</button>}
                    <span className="muted">↔</span>
                    {sb && <button className="cite" onClick={() => onOpen(sb)}>{sb.ref}</button>}
                    <span className="muted small">Le système ne tranche pas : vérifier l'applicabilité.</span>
                  </div>
                </div>
              </div>
            );
          })}
          {a.warnings.map((w) => (
            <p key={w} className="warning">
              {w}
            </p>
          ))}

          <div className="sources-head">
            <span>{a.status === "answered" ? "Sources" : "Passages les plus proches"}</span>
            <span className="muted small">{a.sources.filter((s) => s.cited).length} citée(s) sur {a.sources.length}</span>
          </div>
          <div className="source-grid">
            {[...a.sources]
              .sort((x, y) => Number(y.cited) - Number(x.cited))
              .map((s) => (
                <SourceCard key={s.ref} s={s} onOpen={onOpen} />
              ))}
          </div>
        </div>
      )}
    </section>
  );
}

export function Assistant() {
  const [question, setQuestion] = useState("");
  const [includeSuperseded, setIncludeSuperseded] = useState(false);
  const [family, setFamily] = useState("");
  const [families, setFamilies] = useState<Family[]>([]);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [demo, setDemo] = useState<{ question: string; include_superseded: boolean }[]>([]);
  const [open, setOpen] = useState<Source | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const busy = turns.some((t) => !t.answer && !t.error);

  useEffect(() => {
    api.families().then(setFamilies).catch(() => {});
    api.demoQuestions().then(setDemo).catch(() => {});
  }, []);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns]);

  async function ask(q = question, superseded = includeSuperseded) {
    q = q.trim();
    if (q.length < 3 || busy) return;
    const id = Date.now();
    setTurns((t) => [...t, { id, question: superseded ? `${q} (versions remplacées incluses)` : q }]);
    setQuestion("");
    try {
      const answer = await api.query({ question: q, include_superseded: superseded, family: family || undefined });
      setTurns((t) => t.map((x) => (x.id === id ? { ...x, answer } : x)));
    } catch (e) {
      setTurns((t) => t.map((x) => (x.id === id ? { ...x, error: (e as Error).message } : x)));
    }
  }

  const asked = new Set(turns.map((t) => t.question));
  const label = (d: { question: string; include_superseded: boolean }) =>
    d.include_superseded ? `${d.question} (versions remplacées incluses)` : d.question;
  const picker = (
    <div className="picker">
      <p className="muted small">
        Démo en ligne : réponses pré-calculées par le pipeline réel. Pour poser vos propres questions, lancez le projet en local.
      </p>
      <div className="chips">
        {demo
          .filter((d) => !asked.has(label(d)))
          .map((d) => (
            <button key={label(d)} className="chip" disabled={busy} onClick={() => ask(d.question, d.include_superseded)}>
              {label(d)}
            </button>
          ))}
      </div>
    </div>
  );

  const composer = STATIC_MODE ? picker : (
    <form
      className="composer"
      onSubmit={(e) => {
        e.preventDefault();
        ask();
      }}
    >
      <textarea
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            ask();
          }
        }}
        placeholder="Posez une question sur la documentation (français ou anglais)…"
        rows={2}
      />
      <div className="composer-bar">
        <select value={family} onChange={(e) => setFamily(e.target.value)}>
          <option value="">Toute la base</option>
          {families.map((f) => (
            <option key={f.family} value={f.family}>
              {f.family}
            </option>
          ))}
        </select>
        <label className="toggle">
          <input type="checkbox" checked={includeSuperseded} onChange={(e) => setIncludeSuperseded(e.target.checked)} />
          <span className="track" />
          Versions remplacées
        </label>
        <button className="send" disabled={busy || question.trim().length < 3} aria-label="Envoyer">
          <IconSend />
        </button>
      </div>
    </form>
  );

  return (
    <div className="assistant">
      {turns.length === 0 ? (
        <div className="hero">
          <span className="eyebrow">RAG · documentation aéronautique</span>
          <h1>
            Des réponses <em>sourcées</em>,<br />
            ou pas de réponse du tout.
          </h1>
          <p className="lead">
            Chaque affirmation renvoie au document, à la version et à la page. Si les sources ne suffisent pas, le
            système refuse. Si deux documents divergent, il le signale.
          </p>
          {composer}
          {!STATIC_MODE && (
            <div className="chips">
              {EXAMPLES.map((q) => (
                <button key={q} className="chip" onClick={() => ask(q)}>
                  {q}
                </button>
              ))}
            </div>
          )}
          <p className="muted small corpus-note">Corpus de démonstration fictif : manuel de train d'atterrissage (2 révisions), bulletin de service, manuel hydraulique.</p>
        </div>
      ) : (
        <>
          <div className="thread">
            {turns.map((t) => (
              <TurnView key={t.id} turn={t} onOpen={setOpen} />
            ))}
            <div ref={endRef} />
          </div>
          <div className="dock">{composer}</div>
        </>
      )}
      <SourceDrawer source={open} onClose={() => setOpen(null)} />
    </div>
  );
}
