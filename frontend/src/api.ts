import type { Answer, DocumentInfo, Family, VersionDiff } from "./types";

/** Démo statique (GitHub Pages) : les appels API sont servis par un instantané JSON
 *  produit par backend/scripts/export_static.py avec le vrai pipeline. */
export const STATIC_MODE = import.meta.env.VITE_STATIC === "1";

export interface Health {
  embeddings: string;
  llm_provider: string;
  llm_model: string | null;
  read_only: boolean;
}

interface Snapshot {
  generated_at: string;
  health: Health;
  documents: DocumentInfo[];
  families: Family[];
  diffs: Record<string, VersionDiff>;
  answers: { question: string; include_superseded: boolean; answer: Answer }[];
}

let snapshot: Promise<Snapshot> | null = null;
const loadSnapshot = (): Promise<Snapshot> =>
  (snapshot ??= fetch(`${import.meta.env.BASE_URL}demo/snapshot.json`).then((r) => {
    if (!r.ok) throw new Error("Instantané de démo introuvable.");
    return r.json();
  }));

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, init);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* réponse non JSON */
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

const norm = (q: string) => q.trim().toLowerCase().replace(/[’']/g, "'").replace(/\s+/g, " ");

const live = {
  health: () => request<Health>("/health"),
  documents: () => request<DocumentInfo[]>("/documents"),
  families: () => request<Family[]>("/families"),
  upload: (form: FormData) => request<DocumentInfo>("/documents", { method: "POST", body: form }),
  remove: (id: number) => request<void>(`/documents/${id}`, { method: "DELETE" }),
  query: (body: { question: string; include_superseded: boolean; family?: string }) =>
    request<Answer>("/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  diff: (fromId: number, toId: number) => request<VersionDiff>(`/versions/diff?from_id=${fromId}&to_id=${toId}`),
  fileUrl: (docId: number, page?: number) => `/api/documents/${docId}/file${page ? `#page=${page}` : ""}`,
  demoQuestions: async () => [] as { question: string; include_superseded: boolean }[],
};

const readOnly = () => Promise.reject(new Error("Démo statique : action disponible uniquement en local."));

const offline: typeof live = {
  health: async () => (await loadSnapshot()).health,
  documents: async () => (await loadSnapshot()).documents,
  families: async () => (await loadSnapshot()).families,
  upload: readOnly,
  remove: readOnly,
  query: async ({ question, include_superseded }) => {
    const s = await loadSnapshot();
    const hit =
      s.answers.find((a) => norm(a.question) === norm(question) && a.include_superseded === include_superseded) ??
      s.answers.find((a) => norm(a.question) === norm(question));
    if (!hit) throw new Error("Cette question n'est pas pré-calculée dans la démo en ligne. Choisissez une question proposée, ou lancez le projet en local pour poser les vôtres.");
    await new Promise((r) => setTimeout(r, 450)); // laisse voir l'état « analyse en cours »
    return hit.answer;
  },
  diff: async (fromId, toId) => {
    const d = (await loadSnapshot()).diffs[`${fromId}-${toId}`];
    if (!d) throw new Error("Comparaison non disponible.");
    return d;
  },
  fileUrl: (docId, page) => `${import.meta.env.BASE_URL}demo/pdfs/${docId}.pdf${page ? `#page=${page}` : ""}`,
  demoQuestions: async () => (await loadSnapshot()).answers.map((a) => ({ question: a.question, include_superseded: a.include_superseded })),
};

export const api = STATIC_MODE ? offline : live;
