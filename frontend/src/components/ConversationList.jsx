export default function ConversationList({ conversations, activeId, onSelect, onNew, onDelete }) {
  return (
    <aside className="rail chats" aria-label="Conversations">
      <div className="brand">
        <span className="brand-mark" aria-hidden="true" />
        Knowledge Assistant
      </div>

      <button className="primary full" onClick={onNew}>
        New chat
      </button>

      <nav className="chat-list">
        {conversations.length === 0 && (
          <p className="muted small pad">Your conversations will appear here.</p>
        )}
        {conversations.map((c) => (
          <div key={c.id} className={`chat-item ${c.id === activeId ? "active" : ""}`}>
            <button className="chat-title" onClick={() => onSelect(c.id)} title={c.title}>
              {c.title}
            </button>
            <button
              className="icon-btn"
              aria-label={`Delete conversation: ${c.title}`}
              onClick={() => {
                if (window.confirm("Delete this conversation?")) onDelete(c.id);
              }}
            >
              ×
            </button>
          </div>
        ))}
      </nav>
    </aside>
  );
}
