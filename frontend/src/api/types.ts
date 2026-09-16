// Mirrors odp.models.domain / odp.api.schemas — kept as plain types, not
// generated, since the backend surface is still small and changing.

export type ProjectStatus = "active" | "paused" | "done" | "archived";
export type MeetingStatus =
  | "scheduled"
  | "recorded"
  | "transcribing"
  | "transcribed"
  | "processed"
  | "cancelled";
export type TaskStatus = "todo" | "in_progress" | "done" | "blocked";
export type TaskPriority = "low" | "medium" | "high" | "urgent";
export type ProposalKind = "task" | "decision" | "summary" | "schedule_intent";
export type ProposalStatus = "pending" | "approved" | "edited" | "rejected";
export type JobStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled";
export type JobType = "transcription" | "extraction" | "embedding" | "briefing";

export interface Customer {
  id: string;
  name: string;
  description: string;
  created_at: string;
  updated_at: string;
}

export interface Project {
  id: string;
  customer_id: string | null;
  name: string;
  description: string;
  status: ProjectStatus;
  created_at: string;
  updated_at: string;
}

export interface Meeting {
  id: string;
  project_id: string | null;
  title: string;
  start_utc: string;
  end_utc: string;
  timezone: string;
  rrule: string | null;
  location_link: string | null;
  participants: string[];
  audio_path: string | null;
  status: MeetingStatus;
  created_at: string;
  updated_at: string;
}

export interface TranscriptSegment {
  id: string;
  meeting_id: string;
  seq: number;
  start_ms: number;
  end_ms: number;
  text: string;
  speaker: string | null;
  confidence: number | null;
  no_speech_prob: number | null;
}

export interface Task {
  id: string;
  project_id: string | null;
  meeting_id: string | null;
  title: string;
  description: string;
  owner: string | null;
  due_utc: string | null;
  start_utc: string | null;
  priority: TaskPriority;
  tags: string[];
  status: TaskStatus;
  source_segment_id: string | null;
  confidence: number | null;
  created_at: string;
  updated_at: string;
  checklist_total: number;
  checklist_done: number;
}

export interface ChecklistItem {
  id: string;
  task_id: string;
  title: string;
  done: boolean;
  seq: number;
  created_at: string;
}

export interface Proposal {
  id: string;
  kind: ProposalKind;
  payload: Record<string, unknown>;
  source_meeting_id: string | null;
  source_segment_ids: string[];
  confidence: number | null;
  prompt_version: string;
  model: string;
  status: ProposalStatus;
  resolved_payload: Record<string, unknown> | null;
  resolved_task_id: string | null;
  created_at: string;
  resolved_at: string | null;
}

export interface Job {
  id: string;
  job_type: JobType;
  status: JobStatus;
  payload: Record<string, unknown>;
  progress: number;
  error: string | null;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface TimeSlotOut {
  start_utc: string;
  end_utc: string;
}

export interface ScheduleSuggestResponse {
  target_date: string;
  duration_minutes: number;
  participant_hint: string | null;
  slots: TimeSlotOut[];
}

export interface HealthResponse {
  status: string;
  db: { ok: boolean; path: string };
  ollama: {
    reachable: boolean;
    installed_models?: string[];
    required_models_present: boolean;
    missing_models: string[];
  };
}

export interface ModelSetting {
  active_model: string;
  available_models: string[];
}

export interface DailyActivity {
  date: string;
  created: number;
  completed: number;
}

export interface DashboardStats {
  active_projects: number;
  open_tasks: number;
  overdue_tasks: number;
  meetings: number;
  pending_proposals: number;
  task_status_counts: Record<string, number>;
  weekly_activity: DailyActivity[];
}

export interface ActionItemPayload {
  title: string;
  owner: string | null;
  due_day_of_week: string | null;
  due_explicit_date: string | null;
  source_quote: string;
  confidence: number;
}

export interface DecisionPayload {
  summary: string;
  source_quote: string;
  confidence: number;
}

export interface SummaryPayload {
  summary: string;
}
