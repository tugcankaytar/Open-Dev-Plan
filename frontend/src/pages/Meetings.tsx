import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";

function toLocalInputValue(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(
    date.getHours()
  )}:${pad(date.getMinutes())}`;
}

export default function Meetings() {
  const queryClient = useQueryClient();
  const { data: meetings, isLoading } = useQuery({ queryKey: ["meetings"], queryFn: api.listMeetings });

  const now = new Date();
  const inOneHour = new Date(now.getTime() + 60 * 60 * 1000);
  const [title, setTitle] = useState("");
  const [start, setStart] = useState(toLocalInputValue(now));
  const [end, setEnd] = useState(toLocalInputValue(inOneHour));
  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;

  const createMutation = useMutation({
    mutationFn: () =>
      api.createMeeting({
        title,
        start_utc: new Date(start).toISOString(),
        end_utc: new Date(end).toISOString(),
        timezone,
      }),
    onSuccess: () => {
      setTitle("");
      queryClient.invalidateQueries({ queryKey: ["meetings"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteMeeting(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["meetings"] }),
  });

  const sorted = meetings?.slice().sort((a, b) => b.start_utc.localeCompare(a.start_utc));

  return (
    <div>
      <h1>Toplantılar</h1>

      <form
        className="card inline-form"
        onSubmit={(e) => {
          e.preventDefault();
          if (title.trim()) createMutation.mutate();
        }}
      >
        <input
          placeholder="Toplantı başlığı"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          required
        />
        <label className="field-label">
          Başlangıç
          <input type="datetime-local" value={start} onChange={(e) => setStart(e.target.value)} />
        </label>
        <label className="field-label">
          Bitiş
          <input type="datetime-local" value={end} onChange={(e) => setEnd(e.target.value)} />
        </label>
        <button type="submit" disabled={createMutation.isPending}>
          + Toplantı ekle
        </button>
      </form>

      {isLoading && <p className="muted">Yükleniyor…</p>}
      {sorted?.length === 0 && <p className="muted">Henüz toplantı yok.</p>}

      <table className="data-table">
        <thead>
          <tr>
            <th>Başlık</th>
            <th>Tarih</th>
            <th>Durum</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {sorted?.map((m) => (
            <tr key={m.id}>
              <td>
                <Link to={`/meetings/${m.id}`}>{m.title}</Link>
              </td>
              <td>{new Date(m.start_utc).toLocaleString("tr-TR")}</td>
              <td>
                <span className={`badge badge-${m.status}`}>{m.status}</span>
              </td>
              <td>
                <button className="icon-button" onClick={() => deleteMutation.mutate(m.id)}>
                  ✕
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
