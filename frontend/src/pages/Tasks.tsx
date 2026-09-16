import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api/client";
import type { Task, TaskStatus } from "../api/types";

const COLUMNS: { status: TaskStatus; label: string }[] = [
  { status: "todo", label: "Yapılacak" },
  { status: "in_progress", label: "Devam ediyor" },
  { status: "blocked", label: "Bloke" },
  { status: "done", label: "Tamamlandı" },
];

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

  return (
    <div>
      <h1>Görevler</h1>

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
        />
        <button type="submit" disabled={createMutation.isPending}>
          + Görev ekle
        </button>
      </form>

      {isLoading && <p className="muted">Yükleniyor…</p>}

      <div className="kanban">
        {COLUMNS.map((col) => (
          <div key={col.status} className="kanban-column">
            <h3>
              {col.label}{" "}
              <span className="muted">
                ({tasks?.filter((t) => t.status === col.status).length ?? 0})
              </span>
            </h3>
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
  return (
    <div className="task-card">
      <div className="card-header">
        <strong>{task.title}</strong>
        <button className="icon-button" onClick={onDelete} title="Sil">
          ✕
        </button>
      </div>
      {task.owner && <p className="muted small">{task.owner}</p>}
      {task.due_utc && (
        <p className="muted small">Son tarih: {new Date(task.due_utc).toLocaleDateString("tr-TR")}</p>
      )}
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
