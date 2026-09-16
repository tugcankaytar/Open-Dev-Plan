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
  const [customerIds, setCustomerIds] = useState<string[]>([]);

  const createMutation = useMutation({
    mutationFn: () => api.createProject(name, description, customerIds),
    onSuccess: () => {
      setName("");
      setDescription("");
      setCustomerIds([]);
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });

  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: ProjectStatus }) =>
      api.updateProject(id, { status }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["projects"] }),
  });

  const customerMutation = useMutation({
    mutationFn: ({ id, customer_ids }: { id: string; customer_ids: string[] }) =>
      api.updateProject(id, { customer_ids }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["projects"] }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteProject(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["projects"] }),
  });

  const customerName = (id: string | null) => customers?.find((c) => c.id === id)?.name;

  const toggleId = (ids: string[], id: string) =>
    ids.includes(id) ? ids.filter((existing) => existing !== id) : [...ids, id];

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
        {customers && customers.length > 0 && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: "6px 12px", alignItems: "center" }}>
            {customers.map((c) => (
              <label key={c.id} className="field-label" style={{ flexDirection: "row", gap: 4, alignItems: "center" }}>
                <input
                  type="checkbox"
                  checked={customerIds.includes(c.id)}
                  onChange={() => setCustomerIds((ids) => toggleId(ids, c.id))}
                />
                {c.name}
              </label>
            ))}
          </div>
        )}
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
              {customers && customers.length > 0 && (
                <div style={{ display: "flex", flexWrap: "wrap", gap: "4px 10px" }}>
                  {customers.map((c) => (
                    <label
                      key={c.id}
                      className="field-label"
                      style={{ flexDirection: "row", gap: 4, alignItems: "center", fontSize: 11.5 }}
                    >
                      <input
                        type="checkbox"
                        checked={p.customer_ids.includes(c.id)}
                        onChange={() =>
                          customerMutation.mutate({
                            id: p.id,
                            customer_ids: toggleId(p.customer_ids, c.id),
                          })
                        }
                      />
                      {c.name}
                    </label>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
