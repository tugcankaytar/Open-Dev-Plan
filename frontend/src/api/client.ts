import type {
  ChecklistItem,
  Customer,
  DashboardStats,
  HealthResponse,
  Job,
  Meeting,
  ModelSetting,
  Project,
  ProjectStatus,
  Proposal,
  Task,
  TaskPriority,
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

export interface TaskCreateInput {
  title: string;
  description?: string;
  owner?: string;
  due_utc?: string;
  start_utc?: string;
  priority?: TaskPriority;
  tags?: string[];
  project_id?: string;
  meeting_id?: string;
}

export type TaskUpdateInput = Partial<
  Pick<
    Task,
    "status" | "title" | "description" | "owner" | "due_utc" | "start_utc" | "priority" | "tags" | "project_id"
  >
>;

export const api = {
  health: () => request<HealthResponse>("/health"),

  // --- customers ---
  listCustomers: () => request<Customer[]>("/customers"),
  createCustomer: (name: string, description = "") =>
    request<Customer>("/customers", { method: "POST", body: JSON.stringify({ name, description }) }),
  updateCustomer: (id: string, patch: { name?: string; description?: string }) =>
    request<Customer>(`/customers/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
  deleteCustomer: (id: string) => request<void>(`/customers/${id}`, { method: "DELETE" }),

  // --- projects ---
  listProjects: (customerId?: string) =>
    request<Project[]>(`/projects${customerId ? `?customer_id=${customerId}` : ""}`),
  createProject: (name: string, description = "", customerIds: string[] = []) =>
    request<Project>("/projects", {
      method: "POST",
      body: JSON.stringify({ name, description, customer_ids: customerIds }),
    }),
  updateProject: (
    id: string,
    patch: { status?: ProjectStatus; name?: string; description?: string; customer_ids?: string[] }
  ) => request<Project>(`/projects/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
  deleteProject: (id: string) => request<void>(`/projects/${id}`, { method: "DELETE" }),

  // --- tasks ---
  listTasks: (projectId?: string) =>
    request<Task[]>(`/tasks${projectId ? `?project_id=${projectId}` : ""}`),
  getTask: (id: string) => request<Task>(`/tasks/${id}`),
  createTask: (body: TaskCreateInput) =>
    request<Task>("/tasks", { method: "POST", body: JSON.stringify(body) }),
  updateTask: (id: string, patch: TaskUpdateInput) =>
    request<Task>(`/tasks/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
  deleteTask: (id: string) => request<void>(`/tasks/${id}`, { method: "DELETE" }),
  setTaskStatus: (id: string, status: TaskStatus) =>
    request<Task>(`/tasks/${id}`, { method: "PATCH", body: JSON.stringify({ status }) }),

  // --- task checklist ---
  listChecklist: (taskId: string) => request<ChecklistItem[]>(`/tasks/${taskId}/checklist`),
  addChecklistItem: (taskId: string, title: string) =>
    request<ChecklistItem>(`/tasks/${taskId}/checklist`, {
      method: "POST",
      body: JSON.stringify({ title }),
    }),
  setChecklistItemDone: (itemId: string, done: boolean) =>
    request<void>(`/tasks/checklist/${itemId}`, { method: "PATCH", body: JSON.stringify({ done }) }),
  deleteChecklistItem: (itemId: string) =>
    request<void>(`/tasks/checklist/${itemId}`, { method: "DELETE" }),

  // --- meetings ---
  listMeetings: () => request<Meeting[]>("/meetings"),
  getMeeting: (id: string) => request<Meeting>(`/meetings/${id}`),
  createMeeting: (body: {
    title: string;
    start_utc: string;
    end_utc: string;
    timezone: string;
    customer_id?: string | null;
    location_link?: string;
  }) => request<Meeting>("/meetings", { method: "POST", body: JSON.stringify(body) }),
  updateMeeting: (
    id: string,
    body: Partial<
      Pick<Meeting, "customer_id" | "project_id" | "title" | "status" | "start_utc" | "end_utc">
    >
  ) => request<Meeting>(`/meetings/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
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
  // --- jobs ---
  getJob: (id: string) => request<Job>(`/jobs/${id}`),

  // --- calendar ---
  exportIcsUrl: () => "/api/calendar/export.ics",
  importIcs: (icsText: string, persist: boolean) =>
    request<Meeting[]>("/calendar/import", {
      method: "POST",
      body: JSON.stringify({ ics_text: icsText, persist }),
    }),

  // --- settings ---
  getModelSetting: () => request<ModelSetting>("/settings/model"),
  setModelSetting: (model: string) =>
    request<ModelSetting>("/settings/model", { method: "PUT", body: JSON.stringify({ model }) }),

  // --- stats ---
  getDashboardStats: () => request<DashboardStats>("/stats/dashboard"),
};

export { ApiError };
