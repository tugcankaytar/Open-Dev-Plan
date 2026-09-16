import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { api } from "../api/client";

const NAV_ITEMS = [
  { to: "/", label: "Panel", end: true },
  { to: "/projects", label: "Projeler" },
  { to: "/meetings", label: "Toplantılar" },
  { to: "/tasks", label: "Görevler" },
  { to: "/schedule", label: "Planlama" },
  { to: "/calendar", label: "Takvim" },
];

export default function Layout({ children }: { children: ReactNode }) {
  const { data: health } = useQuery({
    queryKey: ["health"],
    queryFn: api.health,
    refetchInterval: 15_000,
  });

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">Open-Dev-Plan</div>
        <nav>
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="health-badge">
          <span
            className={`dot ${health?.ollama.reachable ? "dot-ok" : "dot-bad"}`}
            title={health?.ollama.reachable ? "Ollama bağlı" : "Ollama bağlantısı yok"}
          />
          <span className="health-text">
            {health ? (health.ollama.reachable ? "Ollama bağlı" : "Ollama kapalı") : "Kontrol ediliyor…"}
          </span>
        </div>
      </aside>
      <main className="content">{children}</main>
    </div>
  );
}
