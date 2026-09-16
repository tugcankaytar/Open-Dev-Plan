import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { IconPlus, IconX } from "../components/icons";
import type { ProjectStatus } from "../api/types";

const STATUS_LABELS: Record<ProjectStatus, string> = {
  active: "Aktif",
  paused: "Duraklatıldı",
  done: "Tamamlandı",
  archived: "Arşivlendi",
};

export default function Projects() {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const customerFilter = searchParams.get("customer_id");

  const { data: projects, isLoading } = useQuery({
    queryKey: ["projects", customerFilter],
    queryFn: () => api.listProjects(customerFilter ?? undefined),
  });
  const { data: customers } = useQuery({ queryKey: ["customers"], queryFn: api.listCustomers });

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [customerId, setCustomerId] = useState("");

  const createMutation = useMutation({
    mutationFn: () => api.createProject(name, description, customerId || null),
    onSuccess: () => {
      setName("");
      setDescription("");
      setCustomerId("");
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });

  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: ProjectStatus }) =>
      api.updateProject(id, { status }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["projects"] }),
  });

  const customerMutation = useMutation({
    mutationFn: ({ id, customer_id }: { id: string; customer_id: string | null }) =>
      api.updateProject(id, { customer_id }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["projects"] }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteProject(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["projects"] }),
  });

  const customerName = (id: string | null) => customers?.find((c) => c.id === id)?.name;

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <h1>Projeler</h1>
        {customerFilter && (
          <button className="secondary" onClick={() => setSearchParams({})}>
            {customerName(customerFilter) ?? "Müşteri"} filtresini kaldır
          </button>
        )}
      </div>

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
        <select value={customerId} onChange={(e) => setCustomerId(e.target.value)}>
          <option value="">Müşteri yok (dahili)</option>
          {customers?.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
        <button type="submit" disabled={createMutation.isPending}>
          <IconPlus size={13} />
          Proje ekle
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
                <IconX size={13} />
              </button>
            </div>
            {p.description && <p className="muted">{p.description}</p>}
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
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
              <select
                value={p.customer_id ?? ""}
                onChange={(e) =>
                  customerMutation.mutate({ id: p.id, customer_id: e.target.value || null })
                }
              >
                <option value="">Müşteri yok (dahili)</option>
                {customers?.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
