import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api/client";
import type { TaskPriority, TaskStatus } from "../api/types";
import { IconCheck, IconPlus, IconX } from "./icons";
import Modal from "./Modal";

const PRIORITY_LABELS: Record<TaskPriority, string> = {
  low: "Düşük",
  medium: "Orta",
  high: "Yüksek",
  urgent: "Acil",
};
const STATUS_LABELS: Record<TaskStatus, string> = {
  todo: "Yapılacak",
  in_progress: "Devam ediyor",
  blocked: "Bloke",
  done: "Tamamlandı",
};

function toDateInputValue(iso: string | null): string {
  return iso ? iso.slice(0, 10) : "";
}

function toIsoDate(dateStr: string, endOfDay: boolean): string | null {
  if (!dateStr) return null;
  return new Date(`${dateStr}T${endOfDay ? "23:59:59" : "09:00:00"}`).toISOString();
}

export default function TaskDetailModal({ taskId, onClose }: { taskId: string; onClose: () => void }) {
  const queryClient = useQueryClient();
  const { data: task } = useQuery({ queryKey: ["task", taskId], queryFn: () => api.getTask(taskId) });
  const { data: checklist } = useQuery({
    queryKey: ["checklist", taskId],
    queryFn: () => api.listChecklist(taskId),
  });
  const { data: projects } = useQuery({ queryKey: ["projects"], queryFn: () => api.listProjects() });

  const [newItem, setNewItem] = useState("");

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["task", taskId] });
    queryClient.invalidateQueries({ queryKey: ["tasks"] });
  };

  const updateMutation = useMutation({
    mutationFn: (patch: Parameters<typeof api.updateTask>[1]) => api.updateTask(taskId, patch),
    onSuccess: invalidate,
  });

  const addItemMutation = useMutation({
    mutationFn: (title: string) => api.addChecklistItem(taskId, title),
    onSuccess: () => {
      setNewItem("");
      queryClient.invalidateQueries({ queryKey: ["checklist", taskId] });
      invalidate();
    },
  });

  const toggleItemMutation = useMutation({
    mutationFn: ({ id, done }: { id: string; done: boolean }) => api.setChecklistItemDone(id, done),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["checklist", taskId] });
      invalidate();
    },
  });

  const deleteItemMutation = useMutation({
    mutationFn: (id: string) => api.deleteChecklistItem(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["checklist", taskId] });
      invalidate();
    },
  });

  const deleteTaskMutation = useMutation({
    mutationFn: () => api.deleteTask(taskId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      onClose();
    },
  });

  if (!task) {
    return (
      <Modal title="Görev" onClose={onClose}>
        <p className="muted">Yükleniyor…</p>
      </Modal>
    );
  }

  return (
    <Modal title={task.title} onClose={onClose} width={560}>
      <div style={{ display: "flex", flexDirection: "column", gap: 13 }}>
        <label className="field-label">
          Başlık
          <input
            value={task.title}
            onChange={(e) => updateMutation.mutate({ title: e.target.value })}
          />
        </label>
        <label className="field-label">
          Açıklama
          <textarea
            rows={2}
            value={task.description}
            onChange={(e) => updateMutation.mutate({ description: e.target.value })}
            style={{ margin: 0 }}
          />
        </label>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <label className="field-label">
            Sorumlu
            <input
              value={task.owner ?? ""}
              onChange={(e) => updateMutation.mutate({ owner: e.target.value || undefined })}
              placeholder="atanmamış"
            />
          </label>
          <label className="field-label">
            Öncelik
            <select
              value={task.priority}
              onChange={(e) => updateMutation.mutate({ priority: e.target.value as TaskPriority })}
            >
              {Object.entries(PRIORITY_LABELS).map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <label className="field-label">
            Başlangıç tarihi
            <input
              type="date"
              value={toDateInputValue(task.start_utc)}
              onChange={(e) => updateMutation.mutate({ start_utc: toIsoDate(e.target.value, false) })}
            />
          </label>
          <label className="field-label">
            Son tarih
            <input
              type="date"
              value={toDateInputValue(task.due_utc)}
              onChange={(e) => updateMutation.mutate({ due_utc: toIsoDate(e.target.value, true) })}
            />
          </label>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <label className="field-label">
            Durum
            <select
              value={task.status}
              onChange={(e) => updateMutation.mutate({ status: e.target.value as TaskStatus })}
            >
              {Object.entries(STATUS_LABELS).map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
          </label>
          <label className="field-label">
            Proje
            <select
              value={task.project_id ?? ""}
              onChange={(e) => updateMutation.mutate({ project_id: e.target.value || undefined })}
            >
              <option value="">Proje yok</option>
              {projects?.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
        </div>

        <label className="field-label">
          Etiketler (virgülle ayır)
          <input
            defaultValue={task.tags.join(", ")}
            onBlur={(e) =>
              updateMutation.mutate({
                tags: e.target.value
                  .split(",")
                  .map((t) => t.trim())
                  .filter(Boolean),
              })
            }
          />
        </label>

        <div>
          <div style={{ fontSize: 12.5, fontWeight: 600, marginBottom: 8 }}>
            Alt görevler {checklist && checklist.length > 0 && `(${checklist.filter((i) => i.done).length}/${checklist.length})`}
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {checklist?.map((item) => (
              <div key={item.id} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <button
                  className="icon-button"
                  style={{
                    width: 22,
                    height: 22,
                    padding: 0,
                    border: "1px solid var(--border)",
                    borderRadius: 6,
                    background: item.done ? "var(--success)" : "transparent",
                  }}
                  onClick={() => toggleItemMutation.mutate({ id: item.id, done: !item.done })}
                  title={item.done ? "Tamamlanmadı olarak işaretle" : "Tamamlandı olarak işaretle"}
                >
                  {item.done && <IconCheck size={12} color="#fff" />}
                </button>
                <span
                  style={{
                    flex: 1,
                    fontSize: 13,
                    textDecoration: item.done ? "line-through" : "none",
                    color: item.done ? "var(--text-faint)" : "var(--text)",
                  }}
                >
                  {item.title}
                </span>
                <button
                  className="icon-button"
                  onClick={() => deleteItemMutation.mutate(item.id)}
                  title="Kaldır"
                >
                  <IconX size={12} />
                </button>
              </div>
            ))}
          </div>
          <form
            style={{ display: "flex", gap: 8, marginTop: 8 }}
            onSubmit={(e) => {
              e.preventDefault();
              if (newItem.trim()) addItemMutation.mutate(newItem.trim());
            }}
          >
            <input
              value={newItem}
              onChange={(e) => setNewItem(e.target.value)}
              placeholder="Alt görev ekle…"
              style={{ flex: 1 }}
            />
            <button type="submit" className="secondary" disabled={!newItem.trim()}>
              <IconPlus size={13} />
            </button>
          </form>
        </div>

        <div className="button-row" style={{ justifyContent: "space-between" }}>
          <button className="danger" onClick={() => deleteTaskMutation.mutate()}>
            <IconX size={13} />
            Görevi sil
          </button>
          <button className="secondary" onClick={onClose}>
            Kapat
          </button>
        </div>
      </div>
    </Modal>
  );
}
