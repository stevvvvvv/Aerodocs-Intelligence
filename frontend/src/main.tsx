import "@fontsource-variable/inter";
import "@fontsource-variable/jetbrains-mono";
import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { STATIC_MODE, api, type Health } from "./api";
import { Assistant } from "./components/Assistant";
import { Documents } from "./components/Documents";
import { Versions } from "./components/Versions";
import { IconChat, IconDocs, IconLayers, IconLock, Logo } from "./icons";
import "./styles.css";

const TABS = [
  { id: "assistant", label: "Assistant", icon: IconChat },
  { id: "documents", label: "Documents", icon: IconDocs },
  { id: "versions", label: "Versions", icon: IconLayers },
] as const;
type Tab = (typeof TABS)[number]["id"];

function App() {
  const [tab, setTab] = useState<Tab>("assistant");
  const [health, setHealth] = useState<Health | null>(null);
  const [down, setDown] = useState(false);

  useEffect(() => {
    api
      .health()
      .then(setHealth)
      .catch(() => setDown(true));
  }, []);

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <Logo />
          <div>
            <strong>AeroDocs</strong>
            <span>Intelligence</span>
          </div>
        </div>
        <nav>
          {TABS.map(({ id, label, icon: Icon }) => (
            <button key={id} className={tab === id ? "active" : ""} onClick={() => setTab(id)}>
              <Icon />
              {label}
            </button>
          ))}
        </nav>
        <div className="system">
          <div className="system-title">Système</div>
          {down ? (
            <div className="sys-row bad">API injoignable</div>
          ) : (
            <>
              <div className="sys-row">
                <span>Embeddings</span>
                <code>{health?.embeddings.replace("local:intfloat/", "") ?? "…"}</code>
              </div>
              <div className="sys-row">
                <span>Génération</span>
                <code>{health ? (health.llm_model ? `${health.llm_provider}:${health.llm_model}` : health.llm_provider) : "…"}</code>
              </div>
              {health?.read_only && (
                <div className="sys-row ro">
                  <IconLock width={14} height={14} /> {STATIC_MODE ? "Démo statique, pré-calculée" : "Démo en lecture seule"}
                </div>
              )}
              {STATIC_MODE && import.meta.env.VITE_REPO_URL && (
                <a className="repo-link" href={import.meta.env.VITE_REPO_URL} target="_blank" rel="noreferrer">
                  Code source sur GitHub →
                </a>
              )}
            </>
          )}
          <p className="disclaimer">
            Aide à la recherche documentaire. Ne remplace ni la documentation approuvée ni le jugement d'un personnel certifié.
          </p>
        </div>
      </aside>
      <main className={tab === "assistant" ? "main main-assistant" : "main"}>
        {tab === "assistant" && <Assistant />}
        {tab === "documents" && <Documents readOnly={!!health?.read_only} />}
        {tab === "versions" && <Versions />}
      </main>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
