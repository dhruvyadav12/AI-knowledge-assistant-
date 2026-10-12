import { useEffect, useRef, useState } from "react";
import Message from "./Message.jsx";

const STARTERS = [
  "Summarize the main points of these documents",
  "List any dates, deadlines or numbers that matter",
  "What risks or open questions are mentioned?",
];

function HealthBanner({ health }) {
  if (!health) return null;
  if (health.api === "down")
    return (
      <div className="banner" role="status">
        The API isn't responding. Start it with <code>uvicorn app.main:app --reload</code> in the backend folder.
      </div>
    );
  if (health.ollama !== "ok")
    return (
      <div className="banner" role="status">
        Ollama isn't running. Start it with <code>ollama serve</code>.
      </div>
    );
  if (health.missing_models?.length)
    return (
      <div className="banner" role="status">
        Missing model{health.missing_models.length > 1 ? "s" : ""}:{" "}
        {health.missing_models.map((m) => (
          <code key={m}>ollama pull {m}</code>
        ))}
      </div>
    );
  return null;
}

export default function Chat({ messages, streaming, health, readyCount, scopeCount, onSend, onStop, onOpenLibrary }) {
  const [draft, setDraft] = useState("");
  const scroller = useRef(null);
  const stick = useRef(true);
  const textarea = useRef(null);

  // Keep the newest text in view unless the reader scrolled up.
  useEffect(() => {
    const el = scroller.current;
    if (el && stick.current) el.scrollTop = el.scrollHeight;
  }, [messages]);

  const onScroll = () => {
    const el = scroller.current;
    stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
  };

  const submit = (text = draft) => {
    const q = text.trim();
    if (!q || streaming) return;
    stick.current = true;
    setDraft("");
    if (textarea.current) textarea.current.style.height = "auto";
    onSend(q);
  };

  const onKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  };

  const grow = (e) => {
    setDraft(e.target.value);
    e.target.style.height = "auto";
    e.target.style.height = `${Math.min(e.target.scrollHeight, 180)}px`;
  };

  const scopeLabel =
    readyCount === 0
      ? "No documents indexed"
      : scopeCount > 0
        ? `Searching ${scopeCount} of ${readyCount} documents`
        : `Searching all ${readyCount} document${readyCount > 1 ? "s" : ""}`;

  return (
    <main className="chat">
      <HealthBanner health={health} />

      <div className="scroller" ref={scroller} onScroll={onScroll}>
        {messages.length === 0 ? (
          <div className="empty">
            <h1>Ask your documents</h1>
            {readyCount === 0 ? (
              <>
                <p>Upload a PDF, Word file or text file, and answers will come with the page they were found on.</p>
                <button className="primary" onClick={onOpenLibrary}>
                  Add documents
                </button>
              </>
            ) : (
              <>
                <p>Answers are written from your documents only, with page references you can open.</p>
                <div className="starters">
                  {STARTERS.map((s) => (
                    <button key={s} className="secondary" onClick={() => submit(s)}>
                      {s}
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>
        ) : (
          <div className="thread">
            {messages.map((m) => (
              <Message key={m.id} message={m} />
            ))}
          </div>
        )}
      </div>

      <div className="composer-wrap">
        <div className="composer">
          <textarea
            ref={textarea}
            rows={1}
            value={draft}
            placeholder="Ask a question about your documents"
            aria-label="Your question"
            onChange={grow}
            onKeyDown={onKeyDown}
          />
          {streaming ? (
            <button className="secondary" onClick={onStop}>
              Stop
            </button>
          ) : (
            <button className="primary" onClick={() => submit()} disabled={!draft.trim()}>
              Ask
            </button>
          )}
        </div>
        <p className="scope-note muted small">{scopeLabel}</p>
      </div>
    </main>
  );
}
