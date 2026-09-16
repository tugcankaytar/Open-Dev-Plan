import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api/client";
import type { TaskPriority } from "../api/types";
import Modal from "./Modal";

const PRIORITY_LABELS: Record<TaskPriority, string> = {
  low: "Düşük",
  medium: "Orta",
  high: "Yüksek",
  urgent: "Acil",
};

function toIsoDate(dateStr: string, endOfDay: boolean): string | undefined {
  if (!dateStr) return undefined;
  return new Date(`${dateStr}T${endOfDay ? "23:59:59" : "09:00:00"}`).toISOString();
}

export default function TaskFormModal({
  onClose,
  defaultProjectId,
}: {
  onClose: () => void;
  defaultProjectId?: string;
}) {
  const queryClient = useQueryClient();
  const { data: customers } = useQuery({ queryKey: ["customers"], queryFn: api.listCustomers });
  const { data: allProjects } = useQuery({ queryKey: ["projects"], queryFn: () => api.listProjects() });

  const [customerId, setCustomerId] = useState("");
  const projects = customerId
    ? allProjects?.filter((p) => p.customer_ids.includes(customerId))
    : allProjects;

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [owner, setOwner] = useState("");
  const [priority, setPriority] = useState<TaskPriority>("medium");
  const [startDate, setStartDate] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [tags, setTags] = useState("");
  const [projectId, setProjectId] = useState(defaultProjectId ?? "");

  const createMutation = useMutation({
    mutationFn: () =>
      api.createTask({
        title,
        description,
        owner: owner || undefined,
        priority,
        start_utc: toIsoDate(startDate, false),
        due_utc: toIsoDate(dueDate, true),
        tags: tags
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean),
        project_id: projectId || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      onClose();
    },
  });

  return (
    <Modal title="Yeni görev" onClose={onClose} width={540}>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (title.trim()) createMutation.mutate();
        }}
        style={{ display: "flex", flexDirection: "column", gap: 13 }}
      >
        <label className="field-label">
          Başlık
          <input value={title} onChange={(e) => setTitle(e.target.value)} required autoFocus />
        </label>
        <label className="field-label">
          Açıklama
          <textarea
            rows={3}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            style={{ margin: 0 }}
          />
        </label>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <label className="field-label">
            Sorumlu
            <input value={owner} onChange={(e) => setOwner(e.target.value)} placeholder="opsiyonel" />
          </label>
          <label className="field-label">
            Öncelik
            <select value={priority} onChange={(e) => setPriority(e.target.value as TaskPriority)}>
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
            <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
          </label>
          <label className="field-label">
            Son tarih
            <input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
          </label>
        </div>
        <label className="field-label">
          Etiketler (virgülle ayır)
          <input value={tags} onChange={(e) => setTags(e.target.value)} placeholder="backend, acil" />
        </label>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <label className="field-label">
            Müşteri
            <select
              value={customerId}
              onChange={(e) => {
                setCustomerId(e.target.value);
                setProjectId("");
              }}
            >
              <option value="">Tümü</option>
              {customers?.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label className="field-label">
            Proje
            <select value={projectId} onChange={(e) => setProjectId(e.target.value)}>
              <option value="">Proje yok</option>
              {projects?.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="button-row">
          <button type="submit" disabled={createMutation.isPending || !title.trim()}>
            Görev oluştur
          </button>
          <button type="button" className="secondary" onClick={onClose}>
            Vazgeç
          </button>
        </div>
      </form>
    </Modal>
  );
}
