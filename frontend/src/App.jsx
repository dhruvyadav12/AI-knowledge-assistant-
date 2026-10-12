import { useCallback, useEffect, useRef, useState } from "react";
import { api, streamAnswer } from "./api.js";
import ConversationList from "./components/ConversationList.jsx";
import Library from "./components/Library.jsx";
import Chat from "./components/Chat.jsx";

export default function App() {
  const [conversations, setConversations] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [scope, setScope] = useState([]); // selected document ids; empty = all
  const [health, setHealth] = useState(null);
  const [streaming, setStreaming] = useState(false);
  const [panel, setPanel] = useState(null); // 'chats' | 'library' | null (small screens)
  const abortRef = useRef(null);

  const refreshConversations = useCallback(
    () => api.listConversations().then(setConversations).catch(() => {}),
    []
  );
  const refreshDocuments = useCallback(
    () => api.listDocuments().then(setDocuments).catch(() => {}),
    []
  );

  useEffect(() => {
    refreshConversations();
    refreshDocuments();
    api.health().then(setHealth).catch(() => setHealth({ api: "down" }));
  }, [refreshConversations, refreshDocuments]);

  // Poll while any document is still being indexed.
  const anyProcessing = documents.some((d) => d.status === "processing");
  useEffect(() => {
    if (!anyProcessing) return;
    const t = setInterval(refreshDocuments, 2000);
    return () => clearInterval(t);
  }, [anyProcessing, refreshDocuments]);

  // Drop scope entries for documents that no longer exist or aren't ready.
  useEffect(() => {
    const ready = new Set(documents.filter((d) => d.status === "ready").map((d) => d.id));
    setScope((s) => (s.every((id) => ready.has(id)) ? s : s.filter((id) => ready.has(id))));
  }, [documents]);

  const openConversation = async (id) => {
    if (streaming) return;
    setPanel(null);
    setActiveId(id);
    const detail = await api.getConversation(id);
    setMessages(detail.messages);
  };

  const newChat = () => {
    if (streaming) return;
    setActiveId(null);
    setMessages([]);
    setPanel(null);
  };

  const removeConversation = async (id) => {
    await api.deleteConversation(id);
    if (id === activeId) newChat();
    refreshConversations();
  };

  const send = async (question) => {
    if (streaming || !question.trim()) return;

    let conversationId = activeId;
    try {
      if (!conversationId) {
        const conv = await api.createConversation();
        conversationId = conv.id;
        setActiveId(conv.id);
      }
    } catch (e) {
      setMessages((m) => [...m, { id: `e${Date.now()}`, role: "assistant", content: "", error: e.message }]);
      return;
    }

    const patchLast = (fn) =>
      setMessages((all) => all.map((m, i) => (i === all.length - 1 ? fn(m) : m)));

    setMessages((all) => [
      ...all,
      { id: `u${Date.now()}`, role: "user", content: question },
      { id: `a${Date.now()}`, role: "assistant", content: "", sources: null, streaming: true },
    ]);
    setStreaming(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await streamAnswer(
        conversationId,
        { question, document_ids: scope.length ? scope : null },
        {
          onSources: (sources) => patchLast((m) => ({ ...m, sources })),
          onToken: (text) => patchLast((m) => ({ ...m, content: m.content + text })),
          onError: (detail) => patchLast((m) => ({ ...m, error: detail })),
        },
        controller.signal
      );
    } catch (e) {
      if (e.name !== "AbortError") patchLast((m) => ({ ...m, error: e.message }));
    } finally {
      patchLast((m) => ({ ...m, streaming: false }));
      setStreaming(false);
      abortRef.current = null;
      refreshConversations();
    }
  };

  const stop = () => abortRef.current?.abort();

  const upload = async (files) => {
    await api.uploadDocuments(files);
    await refreshDocuments();
  };

  const removeDocument = async (id) => {
    await api.deleteDocument(id);
    setScope((s) => s.filter((x) => x !== id));
    refreshDocuments();
  };

  const toggleScope = (id) =>
    setScope((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));

  const readyCount = documents.filter((d) => d.status === "ready").length;

  return (
    <div className={`app ${panel ? `show-${panel}` : ""}`}>
      <header className="topbar">
        <button className="ghost" onClick={() => setPanel(panel === "chats" ? null : "chats")}>
          Chats
        </button>
        <strong className="brand-small">Knowledge Assistant</strong>
        <button className="ghost" onClick={() => setPanel(panel === "library" ? null : "library")}>
          Library{readyCount ? ` (${readyCount})` : ""}
        </button>
      </header>

      {panel && <div className="scrim" onClick={() => setPanel(null)} />}

      <ConversationList
        conversations={conversations}
        activeId={activeId}
        onSelect={openConversation}
        onNew={newChat}
        onDelete={removeConversation}
      />

      <Chat
        messages={messages}
        streaming={streaming}
        health={health}
        readyCount={readyCount}
        scopeCount={scope.length}
        onSend={send}
        onStop={stop}
        onOpenLibrary={() => setPanel("library")}
      />

      <Library
        documents={documents}
        scope={scope}
        onToggleScope={toggleScope}
        onClearScope={() => setScope([])}
        onUpload={upload}
        onDelete={removeDocument}
      />
    </div>
  );
}
