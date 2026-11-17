import type { Answer, DocumentInfo, Family, VersionDiff } from "./types";

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

export const api = {
  health: () => request<{ embeddings: string; llm_provider: string; llm_model: string | null; read_only: boolean }>("/health"),
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
};
