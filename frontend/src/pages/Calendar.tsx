import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api/client";
import { IconDownload } from "../components/icons";

export default function Calendar() {
  const queryClient = useQueryClient();
  const { data: meetings } = useQuery({ queryKey: ["meetings"], queryFn: api.listMeetings });
  const [icsText, setIcsText] = useState("");

  const importMutation = useMutation({
    mutationFn: () => api.importIcs(icsText, true),
    onSuccess: () => {
      setIcsText("");
      queryClient.invalidateQueries({ queryKey: ["meetings"] });
    },
  });

  return (
    <div>
      <h1>Takvim</h1>

      <div className="card">
        <h2>Dışa aktar</h2>
        <p className="muted">Tüm toplantıları tek bir .ics dosyası olarak indir (RRULE dahil).</p>
        <a className="button-link" href={api.exportIcsUrl()} download>
          <IconDownload size={13} />
          .ics indir
        </a>
      </div>

      <div className="card">
        <h2>İçe aktar</h2>
        <p className="muted">
          Başka bir takvimden export ettiğin .ics dosyasının içeriğini buraya yapıştır.
        </p>
        <textarea
          rows={6}
          placeholder="BEGIN:VCALENDAR…"
          value={icsText}
          onChange={(e) => setIcsText(e.target.value)}
        />
        <button onClick={() => importMutation.mutate()} disabled={!icsText.trim() || importMutation.isPending}>
          İçe aktar
        </button>
      </div>

      <div className="card">
        <h2>Tüm toplantılar</h2>
        <table className="data-table">
          <thead>
            <tr>
              <th>Başlık</th>
              <th>Başlangıç</th>
              <th>Bitiş</th>
              <th>Tekrar</th>
            </tr>
          </thead>
          <tbody>
            {meetings?.map((m) => (
              <tr key={m.id}>
                <td>{m.title}</td>
                <td>{new Date(m.start_utc).toLocaleString("tr-TR")}</td>
                <td>{new Date(m.end_utc).toLocaleString("tr-TR")}</td>
                <td>{m.rrule ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
