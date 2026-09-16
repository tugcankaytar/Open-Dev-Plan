import { useEffect, useRef, useState } from "react";
import { useChat } from "../hooks/useChat";
import type { ChatAction } from "../hooks/useChat";
import { IconBot, IconChevronLeft, IconSend, IconTrash } from "./icons";

const SUGGESTED_PROMPTS = [
  "Bu haftanın özeti nedir?",
  "Geciken görevler hangileri?",
  "Yaklaşan toplantılarım neler?",
];

const ACTION_LABELS: Record<string, { pending: string; done: (a: ChatAction) => string }> = {
  create_task: {
    pending: "Görev oluşturuluyor…",
    done: (a) => `Görev oluşturuldu: ${a.arguments.title ?? ""}`,
  },
  update_task_status: {
    pending: "Görev durumu güncelleniyor…",
    done: (a) => `Görev durumu güncellendi: ${a.result?.status ?? ""}`,
  },
  add_checklist_item: {
    pending: "Alt görev ekleniyor…",
    done: (a) => `Alt görev eklendi: ${a.arguments.title ?? ""}`,
  },
  create_meeting: {
    pending: "Toplantı oluşturuluyor…",
    done: (a) => `Toplantı oluşturuldu: ${a.arguments.title ?? ""}`,
  },
};

function describeAction(action: ChatAction): { text: string; failed: boolean } {
  if (action.result?.error) {
    return { text: `İşlem başarısız: ${String(action.result.error)}`, failed: true };
  }
  const meta = ACTION_LABELS[action.name];
  if (!meta) return { text: action.name, failed: false };
  return { text: action.result ? meta.done(action) : meta.pending, failed: false };
}

function readCollapsed(): boolean {
  try {
    return localStorage.getItem("odp.chatCollapsed") === "1";
  } catch {
    return false;
  }
}

function writeCollapsed(value: boolean): void {
  try {
    localStorage.setItem("odp.chatCollapsed", value ? "1" : "0");
  } catch {
    // best-effort only — a private window or blocked storage just means
    // the panel resets to expanded next load, which is a fine default.
  }
}

export default function ChatPanel() {
  const [collapsed, setCollapsed] = useState(readCollapsed);
  const [input, setInput] = useState("");
  const { messages, isStreaming, error, send, clear } = useChat();
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    writeCollapsed(collapsed);
  }, [collapsed]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages]);

  const submit = () => {
    if (!input.trim() || isStreaming) return;
    send(input);
    setInput("");
  };

  if (collapsed) {
    return (
      <div className="chat-panel collapsed">
        <button
          className="chat-rail-toggle"
          onClick={() => setCollapsed(false)}
          title="Asistanı aç"
          aria-label="Asistanı aç"
        >
          <IconBot size={16} />
        </button>
      </div>
    );
  }

  return (
    <div className="chat-panel">
      <div className="chat-header">
        <div className="chat-header-icon">
          <IconBot size={15} />
        </div>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 13.5, fontWeight: 600 }}>Asistan</div>
          <div className="faint" style={{ fontSize: 11 }}>
            Proje verilerinle sohbet et
          </div>
        </div>
        {messages.length > 0 && (
          <button
            className="chat-collapse-btn"
            onClick={clear}
            title="Sohbeti temizle"
            aria-label="Sohbeti temizle"
            disabled={isStreaming}
          >
            <IconTrash size={14} />
          </button>
        )}
        <button
          className="chat-collapse-btn"
          onClick={() => setCollapsed(true)}
          title="Daralt"
          aria-label="Asistanı daralt"
        >
          <IconChevronLeft size={15} />
        </button>
      </div>

      {messages.length === 0 && (
        <div className="chat-chips">
          {SUGGESTED_PROMPTS.map((prompt) => (
            <button key={prompt} className="chat-chip" onClick={() => send(prompt)} type="button">
              {prompt}
            </button>
          ))}
        </div>
      )}

      <div className="chat-messages" ref={scrollRef}>
        {messages.length === 0 && (
          <div className="chat-empty">
            Projeler, görevler, toplantılar ve kararlar hakkında soru sor, ya da doğrudan bir
            işlem yaptır — "Mehmet'e Cuma'ya kadar bir görev oluştur" gibi. Yalnızca
            uygulamandaki gerçek veriye dayanarak çalışır.
          </div>
        )}
        {messages.map((m, i) =>
          m.role === "user" ? (
            <div key={i} className="chat-bubble-user">
              {m.content}
            </div>
          ) : (
            <div key={i} className="chat-bubble-assistant-row" style={{ flexDirection: "column" }}>
              <div style={{ display: "flex", gap: 8 }}>
                <div className="chat-bubble-assistant-icon">
                  <IconBot size={11} />
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  {(m.actions ?? []).map((action, j) => {
                    const { text, failed } = describeAction(action);
                    return (
                      <div
                        key={j}
                        className="pill mono"
                        style={{
                          display: "block",
                          width: "fit-content",
                          marginBottom: 6,
                          background: failed ? "var(--danger-soft)" : "var(--primary-soft)",
                          color: failed ? "var(--danger)" : "var(--primary)",
                        }}
                      >
                        {text}
                      </div>
                    );
                  })}
                  {(m.content || !m.actions?.length) && (
                    <div className="chat-bubble-assistant">
                      {m.content || (isStreaming && i === messages.length - 1 ? "…" : "")}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )
        )}
        {error && <div className="error small">{error}</div>}
      </div>

      <div className="chat-input-row">
        <textarea
          rows={1}
          placeholder="Bir şey sor ya da bir işlem yaptır…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
        />
        <button className="chat-send-btn" onClick={submit} disabled={isStreaming || !input.trim()}>
          <IconSend size={15} />
        </button>
      </div>
    </div>
  );
}
