import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api/client";
import type { ProjectStatus } from "../api/types";

const STATUS_LABELS: Record<ProjectStatus, string> = {
  active: "Aktif",
  paused: "Duraklatıldı",
  done: "Tamamlandı",
  archived: "Arşivlendi",
};

export default function Projects() {
  const queryClient = useQueryClient();
  const { data: projects, isLoading } = useQuery({ queryKey: ["projects"], queryFn: api.listProjects });
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  const createMutation = useMutation({
    mutationFn: () => api.createProject(name, description),
    onSuccess: () => {
      setName("");
      setDescription("");
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });

  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: ProjectStatus }) =>
      api.updateProject(id, { status }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["projects"] }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteProject(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["projects"] }),
  });

  return (
    <div>
      <h1>Projeler</h1>

      <form
        className="card inline-form"
        onSubmit={(e) => {
          e.preventDefault();
          if (name.trim()) createMutation.mutate();
        }}
      >
        <input
          placeholder="Proje adı"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
        <input
          placeholder="Açıklama (opsiyonel)"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
        <button type="submit" disabled={createMutation.isPending}>
          + Proje ekle
        </button>
      </form>

      {isLoading && <p className="muted">Yükleniyor…</p>}
      {projects?.length === 0 && <p className="muted">Henüz proje yok.</p>}

      <div className="card-grid">
        {projects?.map((p) => (
          <div key={p.id} className="card">
            <div className="card-header">
              <h3>{p.name}</h3>
              <button className="icon-button" onClick={() => deleteMutation.mutate(p.id)} title="Sil">
                ✕
              </button>
            </div>
            {p.description && <p className="muted">{p.description}</p>}
            <select
              value={p.status}
              onChange={(e) =>
                statusMutation.mutate({ id: p.id, status: e.target.value as ProjectStatus })
              }
            >
              {Object.entries(STATUS_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>
        ))}
      </div>
    </div>
  );
}
