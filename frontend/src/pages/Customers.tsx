import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { IconPlus, IconX } from "../components/icons";

export default function Customers() {
  const queryClient = useQueryClient();
  const { data: customers, isLoading } = useQuery({ queryKey: ["customers"], queryFn: api.listCustomers });
  const { data: projects } = useQuery({ queryKey: ["projects"], queryFn: () => api.listProjects() });
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  const createMutation = useMutation({
    mutationFn: () => api.createCustomer(name, description),
    onSuccess: () => {
      setName("");
      setDescription("");
      queryClient.invalidateQueries({ queryKey: ["customers"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteCustomer(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["customers"] });
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });

  const projectCountByCustomer = new Map<string, number>();
  for (const p of projects ?? []) {
    for (const customerId of p.customer_ids) {
      projectCountByCustomer.set(customerId, (projectCountByCustomer.get(customerId) ?? 0) + 1);
    }
  }

  return (
    <div>
      <h1>Müşteriler</h1>

      <form
        className="card inline-form"
        onSubmit={(e) => {
          e.preventDefault();
          if (name.trim()) createMutation.mutate();
        }}
      >
        <input
          placeholder="Müşteri adı"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
          style={{ flex: 1, minWidth: 160 }}
        />
        <input
          placeholder="Açıklama (opsiyonel)"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          style={{ flex: 1, minWidth: 160 }}
        />
        <button type="submit" disabled={createMutation.isPending}>
          <IconPlus size={13} />
          Müşteri ekle
        </button>
      </form>

      {isLoading && <p className="muted">Yükleniyor…</p>}
      {customers?.length === 0 && <p className="muted">Henüz müşteri yok.</p>}

      <div className="card-grid">
        {customers?.map((c) => (
          <div key={c.id} className="card">
            <div className="card-header">
              <h3>{c.name}</h3>
              <button className="icon-button" onClick={() => deleteMutation.mutate(c.id)} title="Sil">
                <IconX size={13} />
              </button>
            </div>
            {c.description && <p className="muted small">{c.description}</p>}
            <Link to={`/projects?customer_id=${c.id}`} className="pill mono" style={{ color: "var(--primary)" }}>
              {projectCountByCustomer.get(c.id) ?? 0} proje
            </Link>
          </div>
        ))}
      </div>
    </div>
  );
}
