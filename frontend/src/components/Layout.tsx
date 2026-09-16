import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { api } from "../api/client";
import { useLiveEvents } from "../hooks/useLiveEvents";
import ChatPanel from "./ChatPanel";
import {
  IconBriefcase,
  IconCalendar,
  IconChecklist,
  IconDashboard,
  IconFolder,
  IconMeeting,
} from "./icons";

const NAV_ITEMS = [
  { to: "/", label: "Panel", end: true, Icon: IconDashboard },
  { to: "/customers", label: "Müşteriler", Icon: IconBriefcase },
  { to: "/projects", label: "Projeler", Icon: IconFolder },
  { to: "/meetings", label: "Toplantılar", Icon: IconMeeting },
  { to: "/tasks", label: "Görevler", Icon: IconChecklist },
  { to: "/calendar", label: "Takvim", Icon: IconCalendar },
];

export default function Layout({ children }: { children: ReactNode }) {
  useLiveEvents();
  const queryClient = useQueryClient();
  const { data: health } = useQuery({
    queryKey: ["health"],
    queryFn: api.health,
    refetchInterval: 15_000,
  });
  const { data: modelSetting } = useQuery({
    queryKey: ["model-setting"],
    queryFn: api.getModelSetting,
    refetchInterval: 30_000,
  });

  const setModel = useMutation({
    mutationFn: (model: string) => api.setModelSetting(model),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["model-setting"] }),
  });

  const reachable = health?.ollama.reachable ?? false;
  const options = modelSetting?.available_models.length
    ? modelSetting.available_models
    : modelSetting
      ? [modelSetting.active_model]
      : [];

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none">
              <path d="M4 12L10 18L20 6" stroke="white" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <div className="brand-name">Open-Dev-Plan</div>
        </div>

        <nav>
          {NAV_ITEMS.map(({ to, label, end, Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}
            >
              <Icon size={17} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-spacer" />

        <div className="model-picker" title={reachable ? "Ollama bağlı" : "Ollama bağlantısı yok"}>
          <span className={`model-dot ${reachable ? "ok" : "bad"}`} />
          <div style={{ minWidth: 0, flex: 1 }}>
            {modelSetting ? (
              <select
                value={modelSetting.active_model}
                onChange={(e) => setModel.mutate(e.target.value)}
                disabled={setModel.isPending}
              >
                {!options.includes(modelSetting.active_model) && (
                  <option value={modelSetting.active_model}>{modelSetting.active_model}</option>
                )}
                {options.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            ) : (
              <span style={{ color: "#e6e7ee", fontSize: 12 }}>yükleniyor…</span>
            )}
            <div className="model-picker-sub">{reachable ? "Ollama · aktif model" : "Ollama kapalı"}</div>
          </div>
        </div>
      </aside>

      <main className="content">{children}</main>

      <ChatPanel />
    </div>
  );
}
