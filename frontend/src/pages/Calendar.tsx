import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { IconDownload, IconPlus } from "../components/icons";
import Modal from "../components/Modal";
import MonthCalendar from "../components/MonthCalendar";

const MONTH_LABELS = [
  "Ocak",
  "Şubat",
  "Mart",
  "Nisan",
  "Mayıs",
  "Haziran",
  "Temmuz",
  "Ağustos",
  "Eylül",
  "Ekim",
  "Kasım",
  "Aralık",
];

export default function Calendar() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: meetings } = useQuery({ queryKey: ["meetings"], queryFn: api.listMeetings });

  const today = new Date();
  const [cursor, setCursor] = useState({ year: today.getFullYear(), month: today.getMonth() });
  const [showImport, setShowImport] = useState(false);
  const [icsText, setIcsText] = useState("");

  const importMutation = useMutation({
    mutationFn: () => api.importIcs(icsText, true),
    onSuccess: () => {
      setIcsText("");
      setShowImport(false);
      queryClient.invalidateQueries({ queryKey: ["meetings"] });
    },
  });

  const changeMonth = (delta: number) => {
    setCursor((c) => {
      const d = new Date(c.year, c.month + delta, 1);
      return { year: d.getFullYear(), month: d.getMonth() };
    });
  };

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16, flexWrap: "wrap", gap: 10 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <h1 style={{ marginRight: 6 }}>Takvim</h1>
          <button className="secondary" onClick={() => changeMonth(-1)} style={{ padding: "6px 11px" }}>
            ‹
          </button>
          <div className="display" style={{ fontSize: 14, fontWeight: 600, minWidth: 140, textAlign: "center" }}>
            {MONTH_LABELS[cursor.month]} {cursor.year}
          </div>
          <button className="secondary" onClick={() => changeMonth(1)} style={{ padding: "6px 11px" }}>
            ›
          </button>
          <button
            className="secondary"
            onClick={() => setCursor({ year: today.getFullYear(), month: today.getMonth() })}
          >
            Bugün
          </button>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="secondary" onClick={() => setShowImport(true)}>
            <IconPlus size={13} />
            İçe aktar
          </button>
          <a className="button-link" href={api.exportIcsUrl()} download>
            <IconDownload size={13} />
            .ics indir
          </a>
        </div>
      </div>

      <MonthCalendar
        year={cursor.year}
        month={cursor.month}
        meetings={meetings ?? []}
        onSelectMeeting={(id) => navigate(`/meetings/${id}`)}
      />

      {showImport && (
        <Modal title="Takvim içe aktar" onClose={() => setShowImport(false)}>
          <p className="muted small">
            Başka bir takvimden export ettiğin .ics dosyasının içeriğini buraya yapıştır.
          </p>
          <textarea
            rows={8}
            placeholder="BEGIN:VCALENDAR…"
            value={icsText}
            onChange={(e) => setIcsText(e.target.value)}
          />
          <div className="button-row">
            <button onClick={() => importMutation.mutate()} disabled={!icsText.trim() || importMutation.isPending}>
              İçe aktar
            </button>
            <button className="secondary" onClick={() => setShowImport(false)}>
              Vazgeç
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}
