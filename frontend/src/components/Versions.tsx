import { useEffect, useState } from "react";
import { api } from "../api";
import type { Family, VersionDiff } from "../types";

const LABEL = { added: "Ajoutée", removed: "Supprimée", modified: "Modifiée" };

export function Versions() {
  const [families, setFamilies] = useState<Family[]>([]);
  const [family, setFamily] = useState("");
  const [fromId, setFromId] = useState<number>();
  const [toId, setToId] = useState<number>();
  const [diff, setDiff] = useState<VersionDiff | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.families().then((fs) => {
      const multi = fs.filter((f) => f.versions.length > 1);
      setFamilies(multi);
      if (multi[0]) select(multi[0], true);
    });
  }, []);

  function select(f: Family, autoCompare = false) {
    setFamily(f.family);
    const sorted = [...f.versions].sort((a, b) => (a.effective_date ?? "").localeCompare(b.effective_date ?? ""));
    const a = sorted[sorted.length - 2]?.id;
    const b = sorted[sorted.length - 1]?.id;
    setFromId(a);
    setToId(b);
    setDiff(null);
    if (autoCompare && a && b) compare(a, b);
  }

  async function compare(a = fromId, b = toId) {
    if (!a || !b) return;
    setError(null);
    try {
      setDiff(await api.diff(a, b));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  const versions = families.find((f) => f.family === family)?.versions ?? [];
  const count = (k: "added" | "removed" | "modified") => diff?.changes.filter((c) => c.change === k).length ?? 0;

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <span className="eyebrow">Gestion des versions</span>
          <h2>Qu'est-ce qui a changé entre deux révisions ?</h2>
        </div>
      </header>

      {families.length === 0 ? (
        <p className="muted">Importez au moins deux versions d'un même document pour les comparer.</p>
      ) : (
        <div className="card compare">
          <label>
            Document
            <select value={family} onChange={(e) => select(families.find((f) => f.family === e.target.value)!)}>
              {families.map((f) => (
                <option key={f.family}>{f.family}</option>
              ))}
            </select>
          </label>
          <label>
            De
            <select value={fromId} onChange={(e) => setFromId(Number(e.target.value))}>
              {versions.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.version_label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Vers
            <select value={toId} onChange={(e) => setToId(Number(e.target.value))}>
              {versions.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.version_label}
                </option>
              ))}
            </select>
          </label>
          <button className="btn primary" onClick={() => compare()}>
            Comparer
          </button>
        </div>
      )}
      {error && <p className="error">{error}</p>}

      {diff && (
        <>
          <div className="diff-summary">
            <div className="modified"><strong>{count("modified")}</strong><span>modifiée(s)</span></div>
            <div className="added"><strong>{count("added")}</strong><span>ajoutée(s)</span></div>
            <div className="removed"><strong>{count("removed")}</strong><span>supprimée(s)</span></div>
            <div><strong>{diff.unchanged_sections}</strong><span>inchangée(s)</span></div>
          </div>
          {diff.changes.map((c) => (
            <div key={c.section + c.change} className={`card change ${c.change}`}>
              <div className="change-head">
                <span className={`pill ${c.change}`}>{LABEL[c.change]}</span>
                <strong>{c.section}</strong>
                <span className="mono muted small">
                  {c.page_from ? `p. ${c.page_from}` : "—"} → {c.page_to ? `p. ${c.page_to}` : "—"}
                </span>
              </div>
              <div className="diff">
                {c.diff.map((l, i) => (
                  <div key={i} className={l.startsWith("+") ? "plus" : l.startsWith("-") ? "minus" : ""}>
                    <span className="sign">{l[0]}</span>
                    {l.slice(2)}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </>
      )}
    </div>
  );
}
