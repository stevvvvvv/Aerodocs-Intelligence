import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { IconDocs, IconExternal, IconLock, IconUpload } from "../icons";
import type { DocumentInfo } from "../types";

export function Documents({ readOnly }: { readOnly: boolean }) {
  const [docs, setDocs] = useState<DocumentInfo[]>([]);
  const [busy, setBusy] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [drag, setDrag] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const input = useRef<HTMLInputElement>(null);

  const load = () => api.documents().then(setDocs).catch((e) => setMessage({ ok: false, text: e.message }));
  useEffect(() => {
    load();
  }, []);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!file) return;
    const form = e.currentTarget;
    const data = new FormData(form);
    data.set("file", file);
    for (const k of ["effective_date", "title"]) if (!data.get(k)) data.delete(k);
    setBusy(true);
    setMessage(null);
    try {
      const d = await api.upload(data);
      setMessage({ ok: true, text: `${d.title} (${d.version_label}) importé : ${d.page_count} pages, ${d.chunk_count} passages indexés.` });
      form.reset();
      setFile(null);
      load();
    } catch (err) {
      setMessage({ ok: false, text: (err as Error).message });
    } finally {
      setBusy(false);
    }
  }

  async function remove(d: DocumentInfo) {
    if (!window.confirm(`Supprimer ${d.title} (${d.version_label}) et son index ?`)) return;
    try {
      await api.remove(d.id);
      load();
    } catch (e) {
      setMessage({ ok: false, text: (e as Error).message });
    }
  }

  const families = docs.reduce<Record<string, DocumentInfo[]>>((acc, d) => {
    (acc[d.family] ??= []).push(d);
    return acc;
  }, {});
  const totals = {
    docs: docs.length,
    pages: docs.reduce((n, d) => n + d.page_count, 0),
    chunks: docs.reduce((n, d) => n + d.chunk_count, 0),
  };

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <span className="eyebrow">Base documentaire</span>
          <h2>Documents indexés</h2>
        </div>
        <div className="stats">
          <div><strong>{totals.docs}</strong><span>versions</span></div>
          <div><strong>{totals.pages}</strong><span>pages</span></div>
          <div><strong>{totals.chunks}</strong><span>passages</span></div>
        </div>
      </header>

      {readOnly ? (
        <div className="card readonly">
          <IconLock />
          <div>
            <strong>Démo en lecture seule</strong>
            <p className="muted">
              L'import est désactivé sur la version en ligne. Lancez le projet en local (docker compose) pour indexer vos propres PDF, par exemple les Easy Access Rules de l'EASA.
            </p>
          </div>
        </div>
      ) : (
        <form className="card upload" onSubmit={onSubmit}>
          <div
            className={`dropzone ${drag ? "drag" : ""} ${file ? "has-file" : ""}`}
            onClick={() => input.current?.click()}
            onDragOver={(e) => {
              e.preventDefault();
              setDrag(true);
            }}
            onDragLeave={() => setDrag(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDrag(false);
              const f = e.dataTransfer.files[0];
              if (f) setFile(f);
            }}
          >
            <IconUpload width={22} height={22} />
            <div>
              <strong>{file ? file.name : "Déposez un PDF ou cliquez pour choisir"}</strong>
              <span className="muted small">
                {file ? `${(file.size / 1e6).toFixed(1)} Mo` : "PDF avec couche texte · 200 Mo max"}
              </span>
            </div>
            <input ref={input} type="file" accept="application/pdf" hidden onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          </div>
          <div className="fields">
            <label>
              Famille documentaire
              <input name="family" list="families" placeholder="EAR Continuing Airworthiness" required />
              <datalist id="families">
                {Object.keys(families).map((f) => (
                  <option key={f} value={f} />
                ))}
              </datalist>
            </label>
            <label>
              Version
              <input name="version_label" placeholder="Rev. September 2025" required />
            </label>
            <label>
              Date d'effet
              <input type="date" name="effective_date" />
            </label>
            <label>
              Titre
              <input name="title" placeholder="optionnel" />
            </label>
          </div>
          <div className="upload-foot">
            <p className="muted small">
              La version la plus récente d'une famille devient « en vigueur ». Les précédentes restent consultables, mais sont exclues des réponses par défaut.
            </p>
            <button className="btn primary" disabled={busy || !file}>
              {busy ? "Extraction et indexation…" : "Importer"}
            </button>
          </div>
          {message && <p className={message.ok ? "success" : "error"}>{message.text}</p>}
        </form>
      )}
      {readOnly && message && <p className="error">{message.text}</p>}

      <div className="families">
        {Object.entries(families).map(([family, versions]) => (
          <div key={family} className="card family">
            <div className="family-head">
              <IconDocs />
              <h3>{family}</h3>
              <span className="muted small">{versions.length} version(s)</span>
            </div>
            <ul className="timeline">
              {versions.map((d) => (
                <li key={d.id} className={d.is_current ? "current" : ""}>
                  <span className="node" />
                  <div className="version-main">
                    <strong>{d.version_label}</strong>
                    {d.is_current ? <span className="pill ok-pill">en vigueur</span> : <span className="pill muted-pill">remplacée</span>}
                    <span className="mono muted small">{d.effective_date ?? "date inconnue"}</span>
                  </div>
                  <span className="mono muted small">
                    {d.page_count} p. · {d.chunk_count} passages
                  </span>
                  <div className="row-actions">
                    <a className="icon-link" href={api.fileUrl(d.id)} target="_blank" rel="noreferrer" title="Ouvrir le PDF">
                      <IconExternal width={16} height={16} />
                    </a>
                    {!readOnly && (
                      <button className="link danger" onClick={() => remove(d)}>
                        Supprimer
                      </button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </div>
        ))}
        {docs.length === 0 && <p className="muted">Aucun document : importez un PDF ou lancez le corpus de démonstration.</p>}
      </div>
    </div>
  );
}
