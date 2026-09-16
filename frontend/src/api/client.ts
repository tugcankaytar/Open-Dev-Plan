import type {
  HealthResponse,
  Job,
  Meeting,
  Project,
  ProjectStatus,
  Proposal,
  ScheduleSuggestResponse,
  Task,
  TaskStatus,
  TranscriptSegment,
} from "./types";

class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string
  ) {
    super(detail);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // response body wasn't JSON — keep statusText
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  health: () => request<HealthResponse>("/health"),

  // --- projects ---
  listProjects: () => request<Project[]>("/projects"),
  createProject: (name: string, description = "") =>
    request<Project>("/projects", { method: "POST", body: JSON.stringify({ name, description }) }),
  updateProject: (id: string, patch: { status?: ProjectStatus; name?: string; description?: string }) =>
    request<Project>(`/projects/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
  deleteProject: (id: string) => request<void>(`/projects/${id}`, { method: "DELETE" }),

  // --- tasks ---
  listTasks: (projectId?: string) =>
    request<Task[]>(`/tasks${projectId ? `?project_id=${projectId}` : ""}`),
  createTask: (body: { title: string; description?: string; owner?: string; project_id?: string }) =>
    request<Task>("/tasks", { method: "POST", body: JSON.stringify(body) }),
  updateTask: (id: string, patch: Partial<Pick<Task, "status" | "title" | "owner" | "due_utc">>) =>
    request<Task>(`/tasks/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
  deleteTask: (id: string) => request<void>(`/tasks/${id}`, { method: "DELETE" }),
  setTaskStatus: (id: string, status: TaskStatus) =>
    request<Task>(`/tasks/${id}`, { method: "PATCH", body: JSON.stringify({ status }) }),

  // --- meetings ---
  listMeetings: () => request<Meeting[]>("/meetings"),
  getMeeting: (id: string) => request<Meeting>(`/meetings/${id}`),
  createMeeting: (body: {
    title: string;
    start_utc: string;
    end_utc: string;
    timezone: string;
    location_link?: string;
  }) => request<Meeting>("/meetings", { method: "POST", body: JSON.stringify(body) }),
  deleteMeeting: (id: string) => request<void>(`/meetings/${id}`, { method: "DELETE" }),
  getTranscript: (id: string) => request<TranscriptSegment[]>(`/meetings/${id}/transcript`),
  importTranscriptText: (id: string, text: string) =>
    request<TranscriptSegment[]>(`/meetings/${id}/transcript/import-text`, {
      method: "POST",
      body: JSON.stringify({ text }),
    }),
  getMeetingProposals: (id: string) => request<Proposal[]>(`/meetings/${id}/proposals`),

  // --- ai ---
  triggerExtraction: (meetingId: string) =>
    request<Job>(`/meetings/${meetingId}/extract`, { method: "POST" }),
  resolveProposal: (
    id: string,
    action: "approve" | "edit" | "reject",
    payload?: Record<string, unknown>
  ) =>
    request<Proposal>(`/proposals/${id}/resolve`, {
      method: "POST",
      body: JSON.stringify({ action, payload }),
    }),
  suggestSchedule: (text: string) =>
    request<ScheduleSuggestResponse>("/schedule/suggest", {
      method: "POST",
      body: JSON.stringify({ text }),
    }),

  // --- jobs ---
  getJob: (id: string) => request<Job>(`/jobs/${id}`),

  // --- calendar ---
  exportIcsUrl: () => "/api/calendar/export.ics",
  importIcs: (icsText: string, persist: boolean) =>
    request<Meeting[]>("/calendar/import", {
      method: "POST",
      body: JSON.stringify({ ics_text: icsText, persist }),
    }),
};

export { ApiError };
