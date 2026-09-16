import { DndContext, useDraggable, useDroppable } from "@dnd-kit/core";
import type { DragEndEvent } from "@dnd-kit/core";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api/client";
import { IconDashboard, IconPlus } from "../components/icons";
import TaskDetailModal from "../components/TaskDetailModal";
import TaskFormModal from "../components/TaskFormModal";
import type { Task, TaskStatus } from "../api/types";

const COLUMNS: { status: TaskStatus; label: string; color: string }[] = [
  { status: "todo", label: "Yapılacak", color: "#6E56CF" },
  { status: "in_progress", label: "Devam ediyor", color: "#3fd0e0" },
  { status: "blocked", label: "Bloke", color: "#f2a63a" },
  { status: "done", label: "Tamamlandı", color: "#8b9199" },
];

const AVATAR_COLORS = ["#6E56CF", "#0E9AA7", "#4457C9", "#b5620a", "#8b9199"];
const PRIORITY_META: Record<string, { label: string; color: string; bg: string }> = {
  low: { label: "Düşük", color: "#5b616f", bg: "var(--neutral-soft)" },
  medium: { label: "Orta", color: "#4457C9", bg: "var(--indigo-soft)" },
  high: { label: "Yüksek", color: "var(--amber)", bg: "var(--amber-soft)" },
  urgent: { label: "Acil", color: "var(--danger)", bg: "var(--danger-soft)" },
};

function avatarColorFor(name: string): string {
  let hash = 0;
  for (const ch of name) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
  return AVATAR_COLORS[hash % AVATAR_COLORS.length];
}

function initialsFor(name: string): string {
  const parts = name.trim().split(/\s+/);
  return (parts[0]?.[0] ?? "?").toUpperCase() + (parts[1]?.[0] ?? "").toUpperCase();
}

function dueMeta(dueUtc: string): { text: string; tone: "danger" | "amber" | "success" } {
  const due = new Date(dueUtc);
  const diffDays = Math.floor((due.getTime() - Date.now()) / 86_400_000);
  if (diffDays < 0) return { text: `${Math.abs(diffDays)} gün gecikti`, tone: "danger" };
  if (diffDays === 0) return { text: "Bugün", tone: "danger" };
  if (diffDays <= 3) return { text: due.toLocaleDateString("tr-TR", { day: "numeric", month: "short" }), tone: "amber" };
  return { text: due.toLocaleDateString("tr-TR", { day: "numeric", month: "short" }), tone: "success" };
}

const TONE_STYLES: Record<string, { bg: string; color: string }> = {
  danger: { bg: "var(--danger-soft)", color: "var(--danger)" },
  amber: { bg: "var(--amber-soft)", color: "var(--amber)" },
  success: { bg: "var(--success-soft)", color: "var(--success)" },
};

export default function Tasks() {
  const queryClient = useQueryClient();
  const { data: tasks, isLoading } = useQuery({ queryKey: ["tasks"], queryFn: () => api.listTasks() });
  const [view, setView] = useState<"kanban" | "list">("kanban");
  const [showCreate, setShowCreate] = useState(false);
  const [openTaskId, setOpenTaskId] = useState<string | null>(null);

  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: TaskStatus }) => api.setTaskStatus(id, status),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["tasks"] }),
  });

  const openCount = tasks?.filter((t) => t.status !== "done").length ?? 0;
  const overdueCount =
    tasks?.filter((t) => t.status !== "done" && t.due_utc && new Date(t.due_utc) < new Date()).length ?? 0;

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over) return;
    const newStatus = over.id as TaskStatus;
    const task = tasks?.find((t) => t.id === active.id);
    if (task && task.status !== newStatus) {
      statusMutation.mutate({ id: task.id, status: newStatus });
    }
  };

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 18, flexWrap: "wrap", gap: 10 }}>
        <div>
          <h1>Görevler</h1>
          <div className="muted" style={{ fontSize: 12.5, marginTop: 4 }}>
            {openCount} açık görev{overdueCount > 0 ? ` · ${overdueCount} gecikmiş` : ""}
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div className="view-toggle">
            <button className={view === "kanban" ? "active" : ""} onClick={() => setView("kanban")} type="button">
              Kanban
            </button>
            <button className={view === "list" ? "active" : ""} onClick={() => setView("list")} type="button">
              Liste
            </button>
          </div>
          <button onClick={() => setShowCreate(true)}>
            <IconPlus size={13} />
            Görev ekle
          </button>
        </div>
      </div>

      {isLoading && <p className="muted">Yükleniyor…</p>}

      {view === "kanban" ? (
        <DndContext onDragEnd={handleDragEnd}>
          <div className="kanban">
            {COLUMNS.map((col) => (
              <KanbanColumn
                key={col.status}
                status={col.status}
                label={col.label}
                color={col.color}
                tasks={tasks?.filter((t) => t.status === col.status) ?? []}
                onOpen={setOpenTaskId}
              />
            ))}
          </div>
        </DndContext>
      ) : (
        <div className="card" style={{ padding: 0, overflowX: "auto" }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Başlık</th>
                <th>Sorumlu</th>
                <th>Öncelik</th>
                <th>Son tarih</th>
                <th>Durum</th>
              </tr>
            </thead>
            <tbody>
              {tasks?.map((t) => {
                const p = PRIORITY_META[t.priority];
                const due = t.due_utc ? dueMeta(t.due_utc) : null;
                return (
                  <tr key={t.id} style={{ cursor: "pointer" }} onClick={() => setOpenTaskId(t.id)}>
                    <td>
                      <strong style={{ fontWeight: 500 }}>{t.title}</strong>
                      {t.checklist_total > 0 && (
                        <span className="faint small">
                          {" "}
                          · {t.checklist_done}/{t.checklist_total}
                        </span>
                      )}
                    </td>
                    <td>{t.owner ?? <span className="faint">atanmamış</span>}</td>
                    <td>
                      <span className="pill" style={{ background: p.bg, color: p.color }}>
                        {p.label}
                      </span>
                    </td>
                    <td>
                      {due ? (
                        <span className="pill" style={{ background: TONE_STYLES[due.tone].bg, color: TONE_STYLES[due.tone].color }}>
                          {due.text}
                        </span>
                      ) : (
                        <span className="faint">—</span>
                      )}
                    </td>
                    <td onClick={(e) => e.stopPropagation()}>
                      <select
                        value={t.status}
                        onChange={(e) => statusMutation.mutate({ id: t.id, status: e.target.value as TaskStatus })}
                      >
                        {COLUMNS.map((c) => (
                          <option key={c.status} value={c.status}>
                            {c.label}
                          </option>
                        ))}
                      </select>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {tasks?.length === 0 && (
            <div style={{ padding: 20 }}>
              <p className="muted">Henüz görev yok.</p>
            </div>
          )}
        </div>
      )}

      {showCreate && <TaskFormModal onClose={() => setShowCreate(false)} />}
      {openTaskId && <TaskDetailModal taskId={openTaskId} onClose={() => setOpenTaskId(null)} />}
    </div>
  );
}

function KanbanColumn({
  status,
  label,
  color,
  tasks,
  onOpen,
}: {
  status: TaskStatus;
  label: string;
  color: string;
  tasks: Task[];
  onOpen: (id: string) => void;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: status });

  return (
    <div className="kanban-column" ref={setNodeRef} style={isOver ? { outline: "2px solid var(--primary)" } : undefined}>
      <div className="kanban-column-header">
        <span className="kanban-dot" style={{ background: color }} />
        {label}
        <span className="mono faint" style={{ fontSize: 11, marginLeft: "auto" }}>
          {tasks.length}
        </span>
      </div>
      {tasks.length === 0 ? (
        <div className="faint small" style={{ padding: "8px 4px" }}>
          {status === "done" ? "Henüz tamamlanan yok" : "Buraya sürükle"}
        </div>
      ) : (
        tasks.map((task) => <DraggableTaskCard key={task.id} task={task} onOpen={onOpen} />)
      )}
    </div>
  );
}

function DraggableTaskCard({ task, onOpen }: { task: Task; onOpen: (id: string) => void }) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({ id: task.id });
  const isDone = task.status === "done";
  const due = task.due_utc ? dueMeta(task.due_utc) : null;
  const priority = PRIORITY_META[task.priority];

  return (
    <div
      ref={setNodeRef}
      {...listeners}
      {...attributes}
      onClick={() => onOpen(task.id)}
      className="task-card"
      style={{
        transform: transform ? `translate(${transform.x}px, ${transform.y}px)` : undefined,
        opacity: isDragging ? 0.5 : 1,
        cursor: "grab",
        zIndex: isDragging ? 10 : undefined,
        position: isDragging ? "relative" : undefined,
      }}
    >
      <div className="card-header" style={{ marginBottom: 0 }}>
        <strong
          style={{
            fontSize: 12.5,
            fontWeight: 600,
            lineHeight: 1.4,
            textDecoration: isDone ? "line-through" : "none",
            color: isDone ? "var(--text-muted)" : "var(--text)",
          }}
        >
          {task.title}
        </strong>
      </div>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
        {task.priority !== "medium" && (
          <span className="pill" style={{ background: priority.bg, color: priority.color, fontSize: 10 }}>
            {priority.label}
          </span>
        )}
        {task.checklist_total > 0 && (
          <span className="pill mono" style={{ fontSize: 10 }}>
            <IconDashboard size={9} />
            {task.checklist_done}/{task.checklist_total}
          </span>
        )}
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
    </div>
  );
}
