import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api/client";
import { IconPlus, IconX } from "../components/icons";
import type { Task, TaskStatus } from "../api/types";

const COLUMNS: { status: TaskStatus; label: string; color: string }[] = [
  { status: "todo", label: "Yapılacak", color: "#6E56CF" },
  { status: "in_progress", label: "Devam ediyor", color: "#3fd0e0" },
  { status: "blocked", label: "Bloke", color: "#f2a63a" },
  { status: "done", label: "Tamamlandı", color: "#8b9199" },
];

const AVATAR_COLORS = ["#6E56CF", "#0E9AA7", "#4457C9", "#b5620a", "#8b9199"];

function avatarColorFor(name: string): string {
  let hash = 0;
  for (const ch of name) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
  return AVATAR_COLORS[hash % AVATAR_COLORS.length];
}

function initialsFor(name: string): string {
  const parts = name.trim().split(/\s+/);
  return (parts[0]?.[0] ?? "?").toUpperCase() + (parts[1]?.[0] ?? "").toUpperCase();
}

function dueLabel(dueUtc: string): { text: string; tone: "danger" | "amber" | "success" | "neutral" } {
  const due = new Date(dueUtc);
  const now = new Date();
  const diffDays = Math.floor((due.getTime() - now.getTime()) / 86_400_000);
  if (diffDays < 0) return { text: `${Math.abs(diffDays)} gün gecikti`, tone: "danger" };
  if (diffDays === 0) return { text: "Bugün", tone: "danger" };
  if (diffDays <= 3) return { text: due.toLocaleDateString("tr-TR", { day: "numeric", month: "short" }), tone: "amber" };
  return { text: due.toLocaleDateString("tr-TR", { day: "numeric", month: "short" }), tone: "success" };
}

const TONE_STYLES: Record<string, { bg: string; color: string }> = {
  danger: { bg: "var(--danger-soft)", color: "var(--danger)" },
  amber: { bg: "var(--amber-soft)", color: "var(--amber)" },
  success: { bg: "var(--success-soft)", color: "var(--success)" },
  neutral: { bg: "var(--neutral-soft)", color: "var(--text-muted)" },
};

export default function Tasks() {
  const queryClient = useQueryClient();
  const { data: tasks, isLoading } = useQuery({ queryKey: ["tasks"], queryFn: () => api.listTasks() });
  const [title, setTitle] = useState("");

  const createMutation = useMutation({
    mutationFn: () => api.createTask({ title }),
    onSuccess: () => {
      setTitle("");
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
    },
  });

  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: TaskStatus }) => api.setTaskStatus(id, status),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["tasks"] }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteTask(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["tasks"] }),
  });

  const openCount = tasks?.filter((t) => t.status !== "done").length ?? 0;
  const overdueCount = tasks?.filter((t) => t.status !== "done" && t.due_utc && new Date(t.due_utc) < new Date()).length ?? 0;

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 18 }}>
        <div>
          <h1>Görevler</h1>
          <div className="muted" style={{ fontSize: 12.5, marginTop: 4 }}>
            {openCount} açık görev{overdueCount > 0 ? ` · ${overdueCount} gecikmiş` : ""}
          </div>
        </div>
      </div>

      <form
        className="card inline-form"
        onSubmit={(e) => {
          e.preventDefault();
          if (title.trim()) createMutation.mutate();
        }}
      >
        <input
          placeholder="Yeni görev başlığı"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          required
          style={{ flex: 1, minWidth: 200 }}
        />
        <button type="submit" disabled={createMutation.isPending}>
          <IconPlus size={13} />
          Görev ekle
        </button>
      </form>

      {isLoading && <p className="muted">Yükleniyor…</p>}

      <div className="kanban">
        {COLUMNS.map((col) => (
          <div key={col.status} className="kanban-column">
            <div className="kanban-column-header">
              <span className="kanban-dot" style={{ background: col.color }} />
              {col.label}
              <span className="mono faint" style={{ fontSize: 11, marginLeft: "auto" }}>
                {tasks?.filter((t) => t.status === col.status).length ?? 0}
              </span>
            </div>
            {tasks
              ?.filter((t) => t.status === col.status)
              .map((task) => (
                <TaskCard
                  key={task.id}
                  task={task}
                  onMove={(status) => statusMutation.mutate({ id: task.id, status })}
                  onDelete={() => deleteMutation.mutate(task.id)}
                />
              ))}
          </div>
        ))}
      </div>
    </div>
  );
}

function TaskCard({
  task,
  onMove,
  onDelete,
}: {
  task: Task;
  onMove: (status: TaskStatus) => void;
  onDelete: () => void;
}) {
  const isDone = task.status === "done";
  const due = task.due_utc ? dueLabel(task.due_utc) : null;

  return (
    <div className="task-card">
      <div className="card-header" style={{ marginBottom: 0 }}>
        <strong style={{ fontSize: 12.5, fontWeight: 600, lineHeight: 1.4, textDecoration: isDone ? "line-through" : "none", color: isDone ? "var(--text-muted)" : "var(--text)" }}>
          {task.title}
        </strong>
        <button className="icon-button" onClick={onDelete} title="Sil">
          <IconX size={13} />
        </button>
      </div>
      {task.confidence != null && (
        <div className="ai-tag">
          <svg width="10" height="10" viewBox="0 0 24 24" fill="#8a7edb">
            <path d="M12 3l1.9 5.8H20l-4.95 3.6L16.9 18 12 14.4 7.1 18l1.85-5.6L4 8.8h6.1L12 3Z" />
          </svg>
          Toplantıdan çıkarıldı
        </div>
      )}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        {task.owner ? (
          <span
            title={task.owner}
            style={{
              width: 22,
              height: 22,
              borderRadius: "50%",
              background: avatarColorFor(task.owner),
              color: "#fff",
              fontSize: 9.5,
              fontWeight: 700,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            {initialsFor(task.owner)}
          </span>
        ) : (
          <span className="faint small">atanmamış</span>
        )}
        {due && (
          <span className="pill" style={{ background: TONE_STYLES[due.tone].bg, color: TONE_STYLES[due.tone].color }}>
            {due.text}
          </span>
        )}
      </div>
      <select value={task.status} onChange={(e) => onMove(e.target.value as TaskStatus)}>
        {COLUMNS.map((c) => (
          <option key={c.status} value={c.status}>
            {c.label}
          </option>
        ))}
      </select>
    </div>
  );
}
