import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api/client";
import { IconCheck, IconEdit, IconX } from "../components/icons";
import { useJobStream } from "../hooks/useJobStream";
import type { ActionItemPayload, DecisionPayload, Proposal, SummaryPayload } from "../api/types";

const KIND_LABEL: Record<string, string> = { task: "GÖREV", decision: "KARAR", summary: "ÖZET" };

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
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 18 }}>
        <div>
          <div className="faint" style={{ fontSize: 11.5, marginBottom: 4 }}>
            Toplantılar / <span style={{ color: "var(--text-muted)" }}>{meeting?.title ?? "…"}</span>
          </div>
          <h1>{meeting?.title ?? "Toplantı"}</h1>
          {meeting && (
            <div className="muted" style={{ fontSize: 12.5, marginTop: 5, display: "flex", alignItems: "center", gap: 12 }}>
              <span>
                {new Date(meeting.start_utc).toLocaleString("tr-TR")} · {meeting.timezone}
              </span>
              <span className={`badge badge-${meeting.status}`}>{meeting.status}</span>
            </div>
          )}
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, alignItems: "start" }}>
        <div className="card" style={{ marginBottom: 0 }}>
          <div className="card-header">
            <h2>Transkript</h2>
            {transcript && <span className="pill mono">{transcript.length} segment</span>}
          </div>
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
            <p className="muted small">
              Henüz transkript yok. Ses kaydı/Whisper hattı henüz bağlı değil — aşağıya toplantı
              notlarını yapıştırabilirsin ("İsim: söylenen" biçimindeki satırlar konuşmacıya
              atanır).
            </p>
          )}

          <textarea
            rows={5}
            placeholder={"Ayşe: Demo sunumunu Cuma'ya kadar hazırlayalım.\nMehmet: Tamam, ben hazırlarım."}
            value={pasteText}
            onChange={(e) => setPasteText(e.target.value)}
          />
          <div className="button-row">
            <button
              className="secondary"
              onClick={() => importMutation.mutate()}
              disabled={!pasteText.trim() || importMutation.isPending}
            >
              Transkripti içe aktar
            </button>
            <button
              onClick={() => extractMutation.mutate()}
              disabled={!transcript?.length || extractMutation.isPending || job?.status === "running"}
            >
              {job?.status === "running" || job?.status === "queued" ? "Çıkarılıyor…" : "Özet + aksiyon maddesi çıkar"}
            </button>
          </div>
          {job && (
            <p className="muted small" style={{ marginTop: 8 }}>
              İş durumu: {job.status}
              {job.status === "failed" && job.error ? ` — ${job.error}` : ""}
            </p>
          )}
        </div>

        <div>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10, padding: "0 2px" }}>
            <h2>Öneriler</h2>
            {proposals && proposals.length > 0 && (
              <span className="pill mono" style={{ background: "var(--primary-soft)", color: "var(--primary)" }}>
                {proposals.length} yeni
              </span>
            )}
          </div>
          {proposals?.length === 0 && <p className="muted small">Bekleyen öneri yok — soldan çıkarım çalıştır.</p>}
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
    </div>
  );
}

function ConfidenceBar({ value }: { value: number | null }) {
  if (value == null) return null;
  const pct = Math.round(value * 100);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
      <div style={{ width: 44, height: 5, borderRadius: 3, background: "var(--border-soft)", overflow: "hidden" }}>
        <div style={{ width: `${pct}%`, height: "100%", background: "var(--success)" }} />
      </div>
      <span className="mono faint" style={{ fontSize: 10.5 }}>
        %{pct}
      </span>
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
        confidence={proposal.confidence}
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
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <span className="proposal-kind decision">{KIND_LABEL.decision}</span>
          <ConfidenceBar value={proposal.confidence} />
        </div>
        <div style={{ fontSize: 14, fontWeight: 600, marginTop: 9 }}>{payload.summary}</div>
        <div className="source-quote">&ldquo;{payload.source_quote}&rdquo;</div>
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
      <span className="proposal-kind summary">{KIND_LABEL.summary}</span>
      <div style={{ fontSize: 12.5, color: "#4c5162", lineHeight: 1.6, marginTop: 9 }}>{payload.summary}</div>
      <ProposalActions onApprove={() => resolveMutation.mutate({ action: "approve" })} />
    </div>
  );
}

function TaskProposal({
  payload,
  confidence,
  editing,
  onToggleEdit,
  onApprove,
  onSave,
  onReject,
}: {
  payload: ActionItemPayload;
  confidence: number | null;
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
        <span className="proposal-kind task">GÖREV · düzenleniyor</span>
        <input value={title} onChange={(e) => setTitle(e.target.value)} style={{ marginTop: 9 }} />
        <input value={owner} onChange={(e) => setOwner(e.target.value)} placeholder="Sorumlu (opsiyonel)" />
        <div className="button-row">
          <button onClick={() => onSave({ ...payload, title, owner: owner || null })}>Kaydet ve onayla</button>
          <button className="secondary" onClick={onToggleEdit}>
            Vazgeç
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="proposal-card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <span className="proposal-kind task">{KIND_LABEL.task}</span>
        <ConfidenceBar value={confidence} />
      </div>
      <div style={{ fontSize: 14, fontWeight: 600, marginTop: 9 }}>{payload.title}</div>
      <div className="faint small" style={{ marginTop: 3 }}>
        {payload.owner ?? "atanmamış"}
        {(payload.due_day_of_week || payload.due_explicit_date) &&
          ` · ${payload.due_explicit_date ?? payload.due_day_of_week}`}
      </div>
      <div className="source-quote">&ldquo;{payload.source_quote}&rdquo;</div>
      <div className="button-row">
        <button style={{ flex: 1, justifyContent: "center" }} onClick={onApprove}>
          <IconCheck size={13} />
          Onayla
        </button>
        <button className="secondary" style={{ padding: "8px 11px" }} onClick={onToggleEdit} title="Düzenle">
          <IconEdit size={13} />
        </button>
        <button className="danger" style={{ padding: "8px 11px" }} onClick={onReject} title="Reddet">
          <IconX size={13} />
        </button>
      </div>
    </div>
  );
}

function ProposalActions({ onApprove, onReject }: { onApprove: () => void; onReject?: () => void }) {
  return (
    <div className="button-row">
      <button style={{ flex: 1, justifyContent: "center" }} onClick={onApprove}>
        <IconCheck size={13} />
        Onayla
      </button>
      {onReject && (
        <button className="danger" style={{ padding: "8px 11px" }} onClick={onReject} title="Reddet">
          <IconX size={13} />
        </button>
      )}
    </div>
  );
}
