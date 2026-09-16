import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { StatusDonutChart, WeeklyActivityChart } from "../components/charts";
import { IconCheck, IconChecklist, IconFolder, IconMeeting, IconX } from "../components/icons";
import type { ActionItemPayload, DecisionPayload, Proposal } from "../api/types";

export default function Dashboard() {
  const queryClient = useQueryClient();
  const { data: stats } = useQuery({ queryKey: ["dashboard-stats"], queryFn: api.getDashboardStats });
  const { data: meetings } = useQuery({ queryKey: ["meetings"], queryFn: api.listMeetings });

  const upcoming = meetings
    ?.filter((m) => new Date(m.start_utc).getTime() > Date.now())
    .sort((a, b) => a.start_utc.localeCompare(b.start_utc))
    .slice(0, 5);

  const hour = new Date().getHours();
  const greeting = hour < 6 ? "İyi geceler" : hour < 12 ? "Günaydın" : hour < 18 ? "İyi günler" : "İyi akşamlar";
  const dateLabel = new Date().toLocaleDateString("tr-TR", { weekday: "long", day: "numeric", month: "long" });

  return (
    <div>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 20 }}>
        <div>
          <h1>{greeting}</h1>
          <div className="muted" style={{ fontSize: 13, marginTop: 3 }}>
            {dateLabel}
            {stats && stats.pending_proposals > 0 && ` · ${stats.pending_proposals} onay bekleyen öneri`}
          </div>
        </div>
      </div>

      <div className="stat-grid">
        <Link to="/projects" className="stat-card">
          <div className="stat-icon" style={{ background: "#f1edfc" }}>
            <IconFolder size={15} color="#6E56CF" />
          </div>
          <div className="stat-value">{stats?.active_projects ?? "…"}</div>
          <div className="stat-label">Aktif proje</div>
        </Link>
        <Link to="/tasks" className="stat-card">
          <div className="stat-icon" style={{ background: "#e9fbfc" }}>
            <IconChecklist size={15} color="#0E9AA7" />
          </div>
          <div className="stat-value">{stats?.open_tasks ?? "…"}</div>
          <div className="stat-label">
            Açık görev
            {stats && stats.overdue_tasks > 0 && (
              <span style={{ color: "var(--amber)" }}> · {stats.overdue_tasks} gecikmiş</span>
            )}
          </div>
        </Link>
        <Link to="/meetings" className="stat-card">
          <div className="stat-icon" style={{ background: "#eef1fd" }}>
            <IconMeeting size={15} color="#4457C9" />
          </div>
          <div className="stat-value">{stats?.meetings ?? "…"}</div>
          <div className="stat-label">Toplantı</div>
        </Link>
        <div className="stat-card" style={{ borderColor: "#e3d9fa", background: "linear-gradient(180deg,#faf9ff,#ffffff)" }}>
          <div className="stat-icon" style={{ background: "#f1edfc" }}>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="#6E56CF">
              <path d="M12 3l1.9 5.8H20l-4.95 3.6L16.9 18 12 14.4 7.1 18l1.85-5.6L4 8.8h6.1L12 3Z" />
            </svg>
          </div>
          <div className="stat-value">{stats?.pending_proposals ?? "…"}</div>
          <div className="stat-label">Onay bekleyen öneri</div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1.55fr 1fr", gap: 14, marginBottom: 16 }}>
        <div className="card" style={{ marginBottom: 0 }}>
          <div className="card-header">
            <h2>Haftalık aktivite</h2>
            <div style={{ display: "flex", gap: 14, fontSize: 11.5 }} className="muted">
              <span style={{ display: "flex", alignItems: "center", gap: 5 }}>
                <span style={{ width: 8, height: 8, borderRadius: 2, background: "#6E56CF", display: "inline-block" }} />
                Tamamlanan
              </span>
              <span style={{ display: "flex", alignItems: "center", gap: 5 }}>
                <span style={{ width: 8, height: 8, borderRadius: 2, background: "#c9c0f0", display: "inline-block" }} />
                Oluşturulan
              </span>
            </div>
          </div>
          {stats ? <WeeklyActivityChart data={stats.weekly_activity} /> : <p className="muted">Yükleniyor…</p>}
        </div>

        <div className="card" style={{ marginBottom: 0 }}>
          <h2 style={{ marginBottom: 12 }}>Görev durumu</h2>
          {stats ? <StatusDonutChart counts={stats.task_status_counts} /> : <p className="muted">Yükleniyor…</p>}
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
        <div className="card" style={{ marginBottom: 0 }}>
          <div className="card-header">
            <h2>Yaklaşan toplantılar</h2>
            <Link to="/meetings" style={{ fontSize: 12, fontWeight: 500 }}>
              Tümü →
            </Link>
          </div>
          {upcoming && upcoming.length > 0 ? (
            <div>
              {upcoming.map((m) => {
                const d = new Date(m.start_utc);
                return (
                  <div
                    key={m.id}
                    style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 2px", borderBottom: "1px solid var(--border-soft)" }}
                  >
                    <div style={{ width: 38, textAlign: "center", flexShrink: 0 }}>
                      <div className="mono" style={{ fontSize: 15, fontWeight: 600 }}>
                        {d.getDate()}
                      </div>
                      <div className="faint" style={{ fontSize: 9.5, textTransform: "uppercase" }}>
                        {d.toLocaleDateString("tr-TR", { month: "short" })}
                      </div>
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <Link to={`/meetings/${m.id}`} style={{ fontSize: 13, fontWeight: 500, color: "var(--text)" }}>
                        {m.title}
                      </Link>
                      <div className="faint" style={{ fontSize: 11.5 }}>
                        {d.toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" })}
                        {m.rrule ? " · Tekrarlı" : ""}
                      </div>
                    </div>
                    <span className={`badge badge-${m.status}`}>{m.status}</span>
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="muted">Yaklaşan toplantı yok.</p>
          )}
        </div>

        <PendingProposalsCard
          meetingIds={meetings?.map((m) => m.id) ?? []}
          onChanged={() => queryClient.invalidateQueries({ queryKey: ["dashboard-stats"] })}
        />
      </div>
    </div>
  );
}

function PendingProposalsCard({ meetingIds, onChanged }: { meetingIds: string[]; onChanged: () => void }) {
  const queryClient = useQueryClient();
  const queries = useQuery({
    queryKey: ["all-pending-proposals", meetingIds],
    queryFn: async () => {
      const lists = await Promise.all(meetingIds.map((id) => api.getMeetingProposals(id)));
      return lists.flat();
    },
    enabled: meetingIds.length > 0,
  });

  const resolveMutation = useMutation({
    mutationFn: ({ id, action }: { id: string; action: "approve" | "reject" }) =>
      api.resolveProposal(id, action),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["all-pending-proposals"] });
      onChanged();
    },
  });

  const proposals = (queries.data ?? []).slice(0, 4);

  return (
    <div className="card" style={{ marginBottom: 0 }}>
      <div className="card-header">
        <h2>Onay bekleyen öneriler</h2>
        {proposals.length > 0 && <span className="pill mono" style={{ background: "var(--primary-soft)", color: "var(--primary)" }}>{proposals.length} yeni</span>}
      </div>
      {proposals.length === 0 ? (
        <p className="muted">Bekleyen öneri yok.</p>
      ) : (
        <div className="proposal-list">
          {proposals.map((p) => (
            <ProposalTeaser key={p.id} proposal={p} onResolve={(action) => resolveMutation.mutate({ id: p.id, action })} />
          ))}
        </div>
      )}
    </div>
  );
}

function ProposalTeaser({ proposal, onResolve }: { proposal: Proposal; onResolve: (a: "approve" | "reject") => void }) {
  const isTask = proposal.kind === "task";
  const payload = proposal.payload as unknown as ActionItemPayload & DecisionPayload;
  const title = isTask ? payload.title : payload.summary;
  const subtitle = isTask ? payload.owner ?? "atanmamış" : `%${Math.round((proposal.confidence ?? 0) * 100)} güven`;

  return (
    <div className="proposal-card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
        <div>
          <span className={`proposal-kind ${proposal.kind}`}>
            {proposal.kind === "task" ? "GÖREV" : proposal.kind === "decision" ? "KARAR" : "ÖZET"}
          </span>
          <div style={{ fontSize: 13, fontWeight: 500, marginTop: 6 }}>{title}</div>
          <div className="faint" style={{ fontSize: 11.5, marginTop: 2 }}>{subtitle}</div>
        </div>
        <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
          <button className="secondary" style={{ width: 26, height: 26, padding: 0, justifyContent: "center", borderRadius: 7 }} onClick={() => onResolve("approve")}>
            <IconCheck size={13} color="var(--success)" />
          </button>
          <button className="secondary" style={{ width: 26, height: 26, padding: 0, justifyContent: "center", borderRadius: 7 }} onClick={() => onResolve("reject")}>
            <IconX size={13} color="var(--danger)" />
          </button>
        </div>
      </div>
    </div>
  );
}
