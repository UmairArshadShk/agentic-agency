"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  ApiError,
  createProject,
  decide,
  getProject,
  listProjects,
  streamChat,
  type Decision,
  type Project,
} from "@/lib/api";

type Message = { id: string; role: "user" | "assistant" | "system"; text: string };

const storageKey = (projectId: string) => `agency.messages.${projectId}`;

function loadMessages(projectId: string): Message[] {
  try {
    return JSON.parse(localStorage.getItem(storageKey(projectId)) ?? "[]") as Message[];
  } catch {
    return [];
  }
}

function saveMessages(projectId: string, messages: Message[]) {
  try {
    localStorage.setItem(storageKey(projectId), JSON.stringify(messages));
  } catch {
    // storage unavailable (private window, quota): the chat still works, it just won't persist
  }
}

const newId = () => Math.random().toString(36).slice(2);

const errorText = (error: unknown) => (error instanceof ApiError ? error.message : String(error));

export function ChatApp() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [comment, setComment] = useState("");
  const [newName, setNewName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  const selected = projects.find((p) => p.id === selectedId) ?? null;

  const upsert = useCallback((project: Project) => {
    setProjects((current) =>
      current.some((p) => p.id === project.id)
        ? current.map((p) => (p.id === project.id ? project : p))
        : [...current, project],
    );
  }, []);

  const refresh = useCallback(async () => {
    try {
      setProjects(await listProjects());
      setError(null);
    } catch (e) {
      setError(errorText(e));
    }
  }, []);

  // Load the project list now, and keep it fresh while the page is open.
  useEffect(() => {
    const first = setTimeout(refresh, 0);
    const timer = setInterval(refresh, 5000);
    return () => {
      clearTimeout(first);
      clearInterval(timer);
    };
  }, [refresh]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [messages]);

  function select(project: Project) {
    setSelectedId(project.id);
    setMessages(loadMessages(project.id));
    setComment("");
  }

  function push(projectId: string, next: Message[] | ((current: Message[]) => Message[])) {
    setMessages((current) => {
      const updated = typeof next === "function" ? next(current) : next;
      saveMessages(projectId, updated);
      return updated;
    });
  }

  async function onCreate(event: React.FormEvent) {
    event.preventDefault();
    const name = newName.trim();
    if (!name || busy) return;
    setBusy(true);
    try {
      const project = await createProject(name);
      setNewName("");
      upsert(project);
      setSelectedId(project.id);
      const welcome: Message[] = [
        {
          id: newId(),
          role: "system",
          text: `Project "${project.name}" started. Stages run: ${project.stages.join(", ")}. It is waiting at the approval gate.`,
        },
      ];
      setMessages(welcome);
      saveMessages(project.id, welcome);
      setError(null);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  async function onSend(event: React.FormEvent) {
    event.preventDefault();
    const text = draft.trim();
    if (!text || !selected || busy) return;
    const projectId = selected.id;
    const reply: Message = { id: newId(), role: "assistant", text: "" };
    setDraft("");
    setBusy(true);
    push(projectId, (m) => [...m, { id: newId(), role: "user", text }, reply]);
    try {
      await streamChat(projectId, text, (token) => {
        push(projectId, (m) =>
          m.map((x) => (x.id === reply.id ? { ...x, text: x.text + token } : x)),
        );
      });
      setError(null);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  async function onDecide(decision: Decision) {
    if (!selected || busy) return;
    const projectId = selected.id;
    setBusy(true);
    try {
      const project = await decide(projectId, decision, comment.trim() || undefined);
      upsert(project);
      const verb = decision === "approved" ? "Approved" : "Requested changes";
      push(projectId, (m) => [
        ...m,
        {
          id: newId(),
          role: "system",
          text:
            `${verb}${comment.trim() ? `: ${comment.trim()}` : ""}. ` +
            (project.status === "completed"
              ? "The project finished all stages."
              : "The project is waiting at the approval gate again."),
        },
      ]);
      setComment("");
      setError(null);
    } catch (e) {
      setError(errorText(e));
      // The gate may have been decided elsewhere (another tab): resync.
      try {
        upsert(await getProject(projectId));
      } catch {
        /* keep the first error */
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="app">
      <aside className="sidebar" aria-label="Projects">
        <h1>Agency</h1>
        <form onSubmit={onCreate} className="row">
          <input
            aria-label="New project name"
            placeholder="New project name"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            maxLength={200}
          />
          <button type="submit" disabled={busy || !newName.trim()}>
            Start
          </button>
        </form>
        <ul className="projects">
          {projects.map((p) => (
            <li key={p.id}>
              <button
                className={p.id === selectedId ? "project active" : "project"}
                onClick={() => select(p)}
              >
                <span>{p.name}</span>
                <span className={`badge ${p.status}`}>{p.status.replace("_", " ")}</span>
              </button>
            </li>
          ))}
          {projects.length === 0 && <li className="muted">No projects yet.</li>}
        </ul>
      </aside>

      <main className="main">
        {error && (
          <div role="alert" className="error">
            {error}
          </div>
        )}
        {!selected ? (
          <p className="muted empty">Start or select a project to begin.</p>
        ) : (
          <>
            <header className="header">
              <h2>{selected.name}</h2>
              <div className="stages" aria-label="Stages run">
                {selected.stages.map((s, i) => (
                  <span key={`${s}-${i}`} className="stage">
                    {s}
                  </span>
                ))}
              </div>
            </header>

            <div className="messages" role="log" aria-live="polite" aria-label="Conversation">
              {messages.map((m) => (
                <div key={m.id} className={`message ${m.role}`}>
                  {m.text || "…"}
                </div>
              ))}
              <div ref={endRef} />
            </div>

            {selected.pending_gate && (
              <section className="gate" aria-label="Approval gate">
                <p>
                  <strong>Waiting for your decision</strong> (gate: {selected.pending_gate.gate}
                  {selected.revisions > 0 ? `, revision ${selected.revisions}` : ""})
                </p>
                <input
                  aria-label="Comment for the team"
                  placeholder="Optional comment"
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  maxLength={4000}
                />
                <div className="row">
                  <button disabled={busy} onClick={() => onDecide("approved")}>
                    Approve
                  </button>
                  <button
                    className="secondary"
                    disabled={busy}
                    onClick={() => onDecide("changes_requested")}
                  >
                    Request changes
                  </button>
                </div>
              </section>
            )}

            <form onSubmit={onSend} className="composer row">
              <input
                aria-label="Message"
                placeholder="Type a message"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                maxLength={4000}
              />
              <button type="submit" disabled={busy || !draft.trim()}>
                Send
              </button>
            </form>
          </>
        )}
      </main>
    </div>
  );
}
