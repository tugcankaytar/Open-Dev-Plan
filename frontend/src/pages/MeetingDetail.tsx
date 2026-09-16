import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api/client";
import { useJobStream } from "../hooks/useJobStream";
import type { ActionItemPayload, DecisionPayload, Proposal, SummaryPayload } from "../api/types";

export default function MeetingDetail() {
  // Route is always /meetings/:meetingId, so this is defined whenever the
  // component renders — but hooks must run unconditionally either way, so
  // we don't early-return before the useQuery calls below.
  const { meetingId = "" } = useParams<{ meetingId: string }>();

  const queryClient = useQueryClient();
  const { data: meeting } = useQuery({
    queryKey: ["meeting", meetingId],
    queryFn: () => api.getMeeting(meetingId),
    enabled: !!meetingId,
  });
  const { data: transcript, refetch: refetchTranscript } = useQuery({
    queryKey: ["transcript", meetingId],
    queryFn: () => api.getTranscript(meetingId),
    enabled: !!meetingId,
  });
  const { data: proposals, refetch: refetchProposals } = useQuery({
    queryKey: ["proposals", meetingId],
    queryFn: () => api.getMeetingProposals(meetingId),
    enabled: !!meetingId,
  });

  const [pasteText, setPasteText] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const job = useJobStream(jobId);

  const importMutation = useMutation({
    mutationFn: () => api.importTranscriptText(meetingId, pasteText),
    onSuccess: () => {
      setPasteText("");
      refetchTranscript();
    },
  });

  const extractMutation = useMutation({
    mutationFn: () => api.triggerExtraction(meetingId),
    onSuccess: (job) => setJobId(job.id),
  });

  useEffect(() => {
    if (job?.status === "succeeded") {
      void refetchProposals();
      setJobId(null);
    }
  }, [job?.status, refetchProposals]);

  return (
    <div>
      <h1>{meeting?.title ?? "Toplantı"}</h1>
      {meeting && (
        <p className="muted">
          {new Date(meeting.start_utc).toLocaleString("tr-TR")} · {meeting.timezone} ·{" "}
          <span className={`badge badge-${meeting.status}`}>{meeting.status}</span>
        </p>
      )}

      <div className="card">
        <h2>Transkript</h2>
        {transcript && transcript.length > 0 ? (
          <ul className="transcript">
            {transcript.map((seg) => (
              <li key={seg.id}>
                {seg.speaker && <strong>{seg.speaker}: </strong>}
                {seg.text}
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">
            Henüz transkript yok. Ses kaydı/Whisper hattı henüz bağlı değil — aşağıya toplantı
            notlarını yapıştırabilirsin ("İsim: söylenen" biçimindeki satırlar konuşmacıya
            atanır).
          </p>
        )}

        <textarea
          rows={6}
          placeholder={"Ayşe: Demo sunumunu Cuma'ya kadar hazırlayalım.\nMehmet: Tamam, ben hazırlarım."}
          value={pasteText}
          onChange={(e) => setPasteText(e.target.value)}
        />
        <div className="button-row">
          <button
            onClick={() => importMutation.mutate()}
            disabled={!pasteText.trim() || importMutation.isPending}
          >
            Transkripti içe aktar
          </button>
          <button
            onClick={() => extractMutation.mutate()}
            disabled={!transcript?.length || extractMutation.isPending || job?.status === "running"}
          >
            {job?.status === "running" || job?.status === "queued"
              ? "Çıkarılıyor…"
              : "Özet + aksiyon maddesi çıkar (gerçek LLM)"}
          </button>
        </div>
        {job && (
          <p className="muted">
            İş durumu: {job.status}
            {job.status === "failed" && job.error ? ` — ${job.error}` : ""}
          </p>
        )}
      </div>

      <div className="card">
        <h2>Öneriler (onay bekleyen)</h2>
        {proposals?.length === 0 && (
          <p className="muted">Bekleyen öneri yok — yukarıdan çıkarım çalıştır.</p>
        )}
        <div className="proposal-list">
          {proposals?.map((p) => (
            <ProposalCard
              key={p.id}
              proposal={p}
              onResolved={() => queryClient.invalidateQueries({ queryKey: ["proposals", meetingId] })}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

function ProposalCard({ proposal, onResolved }: { proposal: Proposal; onResolved: () => void }) {
  const [editing, setEditing] = useState(false);
  const resolveMutation = useMutation({
    mutationFn: (args: { action: "approve" | "edit" | "reject"; payload?: Record<string, unknown> }) =>
      api.resolveProposal(proposal.id, args.action, args.payload),
    onSuccess: onResolved,
  });

  if (proposal.kind === "task") {
    const payload = proposal.payload as unknown as ActionItemPayload;
    return (
      <TaskProposal
        payload={payload}
        editing={editing}
        onToggleEdit={() => setEditing((v) => !v)}
        onApprove={() => resolveMutation.mutate({ action: "approve" })}
        onSave={(edited) =>
          resolveMutation.mutate({ action: "edit", payload: edited as unknown as Record<string, unknown> })
        }
        onReject={() => resolveMutation.mutate({ action: "reject" })}
      />
    );
  }

  if (proposal.kind === "decision") {
    const payload = proposal.payload as unknown as DecisionPayload;
    return (
      <div className="proposal-card">
        <span className="proposal-kind">Karar</span>
        <p>{payload.summary}</p>
        <p className="muted small">"{payload.source_quote}"</p>
        <ProposalActions
          onApprove={() => resolveMutation.mutate({ action: "approve" })}
          onReject={() => resolveMutation.mutate({ action: "reject" })}
        />
      </div>
    );
  }

  const payload = proposal.payload as unknown as SummaryPayload;
  return (
    <div className="proposal-card">
      <span className="proposal-kind">Özet</span>
      <p>{payload.summary}</p>
      <ProposalActions
        onApprove={() => resolveMutation.mutate({ action: "approve" })}
        onReject={() => resolveMutation.mutate({ action: "reject" })}
      />
    </div>
  );
}

function TaskProposal({
  payload,
  editing,
  onToggleEdit,
  onApprove,
  onSave,
  onReject,
}: {
  payload: ActionItemPayload;
  editing: boolean;
  onToggleEdit: () => void;
  onApprove: () => void;
  onSave: (edited: ActionItemPayload) => void;
  onReject: () => void;
}) {
  const [title, setTitle] = useState(payload.title);
  const [owner, setOwner] = useState(payload.owner ?? "");

  if (editing) {
    return (
      <div className="proposal-card">
        <span className="proposal-kind">Görev (düzenleniyor)</span>
        <input value={title} onChange={(e) => setTitle(e.target.value)} />
        <input
          value={owner}
          onChange={(e) => setOwner(e.target.value)}
          placeholder="Sorumlu (opsiyonel)"
        />
        <div className="button-row">
          <button onClick={() => onSave({ ...payload, title, owner: owner || null })}>
            Kaydet ve onayla
          </button>
          <button className="secondary" onClick={onToggleEdit}>
            Vazgeç
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="proposal-card">
      <span className="proposal-kind">Görev</span>
      <p>
        <strong>{payload.title}</strong>
        {payload.owner && <> — {payload.owner}</>}
      </p>
      {(payload.due_day_of_week || payload.due_explicit_date) && (
        <p className="muted small">
          Son tarih: {payload.due_explicit_date ?? payload.due_day_of_week}
        </p>
      )}
      <p className="muted small">"{payload.source_quote}"</p>
      <div className="button-row">
        <button onClick={onApprove}>Onayla</button>
        <button className="secondary" onClick={onToggleEdit}>
          Düzenle
        </button>
        <button className="danger" onClick={onReject}>
          Reddet
        </button>
      </div>
    </div>
  );
}

function ProposalActions({ onApprove, onReject }: { onApprove: () => void; onReject: () => void }) {
  return (
    <div className="button-row">
      <button onClick={onApprove}>Onayla</button>
      <button className="danger" onClick={onReject}>
        Reddet
      </button>
    </div>
  );
}
