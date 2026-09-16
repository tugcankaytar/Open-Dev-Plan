import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api/client";
import type { ScheduleSuggestResponse, TimeSlotOut } from "../api/types";

export default function Schedule() {
  const [text, setText] = useState("");
  const [result, setResult] = useState<ScheduleSuggestResponse | null>(null);
  const [meetingTitle, setMeetingTitle] = useState("");
  const [created, setCreated] = useState<string | null>(null);

  const suggestMutation = useMutation({
    mutationFn: () => api.suggestSchedule(text),
    onSuccess: (res) => {
      setResult(res);
      setCreated(null);
    },
  });

  const createMutation = useMutation({
    mutationFn: (slot: TimeSlotOut) =>
      api.createMeeting({
        title: meetingTitle || text.slice(0, 60),
        start_utc: slot.start_utc,
        end_utc: slot.end_utc,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      }),
    onSuccess: (meeting) => setCreated(meeting.id),
  });

  return (
    <div>
      <h1>Planlama</h1>
      <p className="muted">
        Doğal dilden bir toplantı isteği yaz — model sadece süre/gün gibi niyeti ayrıştırır;
        çakışmasız slot bulma tamamen deterministik kodla yapılır, LLM tarih hesaplamaz (bkz.
        README).
      </p>

      <form
        className="card inline-form"
        onSubmit={(e) => {
          e.preventDefault();
          if (text.trim()) suggestMutation.mutate();
        }}
      >
        <input
          placeholder="Örn: Cuma günü 1.5 saatlik bir toplantı, öğleden sonra"
          value={text}
          onChange={(e) => setText(e.target.value)}
          style={{ flex: 1 }}
          required
        />
        <button type="submit" disabled={suggestMutation.isPending}>
          {suggestMutation.isPending ? "Aranıyor…" : "Slot öner"}
        </button>
      </form>

      {suggestMutation.isError && (
        <p className="error">Öneri alınamadı — Ollama çalışıyor mu kontrol et.</p>
      )}

      {result && (
        <div className="card">
          <h2>{result.target_date}</h2>
          <p className="muted">
            Süre: {result.duration_minutes} dk
            {result.participant_hint ? ` · Katılımcı: ${result.participant_hint}` : ""}
          </p>

          {result.slots.length === 0 ? (
            <p className="muted">Bu gün için uygun boş slot bulunamadı.</p>
          ) : (
            <>
              <input
                placeholder="Toplantı başlığı (opsiyonel)"
                value={meetingTitle}
                onChange={(e) => setMeetingTitle(e.target.value)}
              />
              <ul className="plain-list">
                {result.slots.map((slot, i) => (
                  <li key={i} className="slot-row">
                    <span>
                      {new Date(slot.start_utc).toLocaleTimeString("tr-TR", {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}{" "}
                      –{" "}
                      {new Date(slot.end_utc).toLocaleTimeString("tr-TR", {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </span>
                    <button onClick={() => createMutation.mutate(slot)} disabled={createMutation.isPending}>
                      Bu slotta toplantı oluştur
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}

      {created && <p className="success">Toplantı oluşturuldu — Toplantılar sayfasında görebilirsin.</p>}
    </div>
  );
}
