import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";

export default function Dashboard() {
  const { data: projects } = useQuery({ queryKey: ["projects"], queryFn: api.listProjects });
  const { data: tasks } = useQuery({ queryKey: ["tasks"], queryFn: () => api.listTasks() });
  const { data: meetings } = useQuery({ queryKey: ["meetings"], queryFn: api.listMeetings });

  const openTasks = tasks?.filter((t) => t.status !== "done").length ?? 0;
  const upcoming = meetings
    ?.filter((m) => new Date(m.start_utc).getTime() > Date.now())
    .sort((a, b) => a.start_utc.localeCompare(b.start_utc))
    .slice(0, 5);

  return (
    <div>
      <h1>Panel</h1>
      <div className="stat-grid">
        <StatCard label="Proje" value={projects?.length ?? "…"} to="/projects" />
        <StatCard label="Açık görev" value={openTasks} to="/tasks" />
        <StatCard label="Toplantı" value={meetings?.length ?? "…"} to="/meetings" />
      </div>

      <div className="card">
        <h2>Yaklaşan toplantılar</h2>
        {upcoming && upcoming.length > 0 ? (
          <ul className="plain-list">
            {upcoming.map((m) => (
              <li key={m.id}>
                <Link to={`/meetings/${m.id}`}>{m.title}</Link>
                <span className="muted"> — {new Date(m.start_utc).toLocaleString("tr-TR")}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">Yaklaşan toplantı yok.</p>
        )}
      </div>

      <div className="card">
        <h2>Başlarken</h2>
        <ol className="steps">
          <li>
            <Link to="/meetings">Toplantılar</Link> sayfasından bir toplantı oluştur.
          </li>
          <li>Toplantı detayına git, transkript metnini yapıştır (ses kaydı henüz bağlı değil).</li>
          <li>"Çıkar" düğmesine bas — gerçek yerel LLM aksiyon maddesi/karar/özet çıkarır.</li>
          <li>Önerileri incele, onayla/düzenle/reddet — onaylanan aksiyon maddeleri göreve dönüşür.</li>
        </ol>
      </div>
    </div>
  );
}

function StatCard({ label, value, to }: { label: string; value: number | string; to: string }) {
  return (
    <Link to={to} className="stat-card">
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
    </Link>
  );
}
