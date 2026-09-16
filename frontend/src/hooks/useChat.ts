import { useCallback, useRef, useState } from "react";

export interface ChatAction {
  name: string;
  arguments: Record<string, unknown>;
  result?: Record<string, unknown>;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  actions?: ChatAction[];
}

interface ChatSseEvent {
  delta?: string;
  tool_call?: { name: string; arguments: Record<string, unknown> };
  tool_result?: { name: string } & Record<string, unknown>;
  done?: boolean;
  error?: string;
}

/** Streams a chat reply from POST /api/chat by reading the response body
 * as a stream (not EventSource — the request needs a body, and
 * EventSource only issues GET). Parses the same `data: {...}\n\n` shape
 * the backend's other SSE endpoints use, including tool-call/tool-result
 * events when the assistant performs an action. */
export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const send = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || isStreaming) return;

      setError(null);
      const history = messages.slice(-16).map((m) => ({ role: m.role, content: m.content }));
      setMessages((prev) => [
        ...prev,
        { role: "user", content: trimmed },
        { role: "assistant", content: "", actions: [] },
      ]);
      setIsStreaming(true);

      const controller = new AbortController();
      abortRef.current = controller;

      const updateLastAssistant = (fn: (msg: ChatMessage) => ChatMessage) => {
        setMessages((prev) => {
          const next = [...prev];
          const last = next[next.length - 1];
          if (last && last.role === "assistant") {
            next[next.length - 1] = fn(last);
          }
          return next;
        });
      };

      try {
        const response = await fetch("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: trimmed, history }),
          signal: controller.signal,
        });
        if (!response.ok || !response.body) {
          throw new Error(`chat request failed: ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          const events = buffer.split("\n\n");
          buffer = events.pop() ?? "";

          for (const rawEvent of events) {
            const line = rawEvent.split("\n").find((l) => l.startsWith("data: "));
            if (!line) continue;
            const payload = JSON.parse(line.slice("data: ".length)) as ChatSseEvent;

            if (payload.error) {
              setError(payload.error);
            } else if (payload.delta) {
              const delta = payload.delta;
              updateLastAssistant((msg) => ({ ...msg, content: msg.content + delta }));
            } else if (payload.tool_call) {
              const { name, arguments: args } = payload.tool_call;
              updateLastAssistant((msg) => ({
                ...msg,
                actions: [...(msg.actions ?? []), { name, arguments: args }],
              }));
            } else if (payload.tool_result) {
              const { name, ...result } = payload.tool_result;
              updateLastAssistant((msg) => {
                const actions = [...(msg.actions ?? [])];
                // Manual reverse scan (not Array.findLastIndex — ES2023,
                // outside this project's target lib) for the most recent
                // pending call of this name.
                let idx = -1;
                for (let i = actions.length - 1; i >= 0; i--) {
                  if (actions[i].name === name && !actions[i].result) {
                    idx = i;
                    break;
                  }
                }
                if (idx !== -1) actions[idx] = { ...actions[idx], result };
                return { ...msg, actions };
              });
            }
          }
        }
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          setError("Bağlantı hatası — Ollama çalışıyor mu kontrol et.");
        }
      } finally {
        setIsStreaming(false);
        abortRef.current = null;
      }
    },
    [messages, isStreaming]
  );

  const stop = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const clear = useCallback(() => {
    abortRef.current?.abort();
    setMessages([]);
    setError(null);
    setIsStreaming(false);
  }, []);

  return { messages, isStreaming, error, send, stop, clear };
}
