import { createSseParser } from "./sse";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export type Gate = { gate: string; project_id: string };

export type Project = {
  id: string;
  name: string;
  status: string;
  graph_version: number;
  created_at: string;
  stages: string[];
  revisions: number;
  pending_gate: Gate | null;
};

export type Decision = "approved" | "changes_requested";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { "content-type": "application/json", ...init?.headers },
    });
  } catch {
    throw new ApiError(0, `Cannot reach the API at ${API_URL}. Is it running (make api)?`);
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = typeof body?.detail === "string" ? body.detail : response.statusText;
    throw new ApiError(response.status, detail);
  }
  return response.json() as Promise<T>;
}

export const listProjects = () => request<Project[]>("/projects");

export const getProject = (id: string) => request<Project>(`/projects/${id}`);

export const createProject = (name: string) =>
  request<Project>("/projects", { method: "POST", body: JSON.stringify({ name }) });

export const decide = (id: string, decision: Decision, comment?: string) =>
  request<Project>(`/projects/${id}/approvals`, {
    method: "POST",
    body: JSON.stringify({ decision, comment: comment || null }),
  });

/** Send a chat message and call onToken for each streamed chunk. Resolves when the stream ends. */
export async function streamChat(
  id: string,
  message: string,
  onToken: (text: string) => void,
  signal?: AbortSignal,
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}/projects/${id}/chat`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ message }),
      signal,
    });
  } catch {
    throw new ApiError(0, `Cannot reach the API at ${API_URL}. Is it running (make api)?`);
  }
  if (!response.ok || !response.body) {
    throw new ApiError(response.status, response.statusText || "chat failed");
  }
  const feed = createSseParser((event) => {
    if (event.event === "token") onToken((event.data as { text: string }).text);
  });
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    feed(decoder.decode(value, { stream: true }));
  }
}
