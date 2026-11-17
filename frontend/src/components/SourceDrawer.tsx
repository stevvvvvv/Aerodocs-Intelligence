import { useEffect, useState } from "react";
import { api } from "../api";
import { IconExternal, IconX } from "../icons";
import type { Source } from "../types";

export function pagesLabel(s: Source) {
  return s.page_start === s.page_end ? `p. ${s.page_start}` : `p. ${s.page_start}–${s.page_end}`;
}

export function SourceDrawer({ source, onClose }: { source: Source | null; onClose: () => void }) {
  const [tab, setTab] = useState<"excerpt" | "pdf">("excerpt");

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  useEffect(() => setTab("excerpt"), [source?.chunk_id]);

  return (
    <>
      <div className={`scrim ${source ? "open" : ""}`} onClick={onClose} />
      <aside className={`drawer ${source ? "open" : ""}`} aria-hidden={!source}>
        {source && (
          <>
            <div className="drawer-head">
              <div>
                <div className="eyebrow">
                  <span className="ref-badge">{source.ref}</span>
                  {source.version_label} · {pagesLabel(source)}
                  {!source.is_current && <span className="pill muted-pill">version remplacée</span>}
                </div>
                <h3>{source.title}</h3>
                <p className="muted">{source.section ?? "Section non détectée"}</p>
              </div>
              <button className="icon-btn" onClick={onClose} aria-label="Fermer">
                <IconX />
              </button>
            </div>
            <div className="segmented">
              <button className={tab === "excerpt" ? "on" : ""} onClick={() => setTab("excerpt")}>
                Passage indexé
              </button>
              <button className={tab === "pdf" ? "on" : ""} onClick={() => setTab("pdf")}>
                Page du PDF
              </button>
            </div>
            {tab === "excerpt" ? (
              <div className="drawer-body">
                <pre className="excerpt">{source.excerpt}</pre>
                <div className="meta-grid">
                  <div>
                    <span>Similarité</span>
                    <strong>{source.similarity.toFixed(3)}</strong>
                  </div>
                  <div>
                    <span>Famille</span>
                    <strong>{source.family}</strong>
                  </div>
                  <div>
                    <span>Citée dans la réponse</span>
                    <strong>{source.cited ? "Oui" : "Non"}</strong>
                  </div>
                </div>
              </div>
            ) : (
              <iframe
                className="pdf-frame"
                title="PDF source"
                src={api.fileUrl(source.document_id, source.page_start)}
              />
            )}
            <a className="btn ghost" href={api.fileUrl(source.document_id, source.page_start)} target="_blank" rel="noreferrer">
              Ouvrir le PDF à la page {source.page_start} <IconExternal width={15} height={15} />
            </a>
          </>
        )}
      </aside>
    </>
  );
}
