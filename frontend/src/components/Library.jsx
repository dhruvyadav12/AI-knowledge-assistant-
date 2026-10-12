import { useRef, useState } from "react";

const ACCEPT = ".pdf,.docx,.txt,.md";

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export default function Library({ documents, scope, onToggleScope, onClearScope, onUpload, onDelete }) {
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const handleFiles = async (fileList) => {
    const files = Array.from(fileList || []);
    if (!files.length) return;
    setBusy(true);
    setError(null);
    try {
      await onUpload(files);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  return (
    <aside className="rail library" aria-label="Document library">
      <div className="rail-head">
        <h2>Library</h2>
        {scope.length > 0 && (
          <button className="link" onClick={onClearScope}>
            Search all
          </button>
        )}
      </div>

      <div
        className={`dropzone ${dragging ? "drag" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          handleFiles(e.dataTransfer.files);
        }}
      >
        <p>{busy ? "Uploading…" : "Drop files here"}</p>
        <p className="muted small">PDF, DOCX, TXT or Markdown</p>
        <button className="secondary" disabled={busy} onClick={() => inputRef.current?.click()}>
          Choose files
        </button>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT}
          multiple
          hidden
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>
      {error && <p className="error small" role="alert">{error}</p>}

      <ul className="doc-list">
        {documents.length === 0 && (
          <li className="muted small pad">No documents yet. Upload one to start asking questions.</li>
        )}
        {documents.map((d) => {
          const ready = d.status === "ready";
          return (
            <li key={d.id} className={`doc ${d.status}`}>
              <label className="doc-main">
                <input
                  type="checkbox"
                  disabled={!ready}
                  checked={scope.includes(d.id)}
                  onChange={() => onToggleScope(d.id)}
                  aria-label={`Only search ${d.filename}`}
                />
                <span className="doc-text">
                  <span className="doc-name" title={d.filename}>{d.filename}</span>
                  <span className="doc-meta">
                    {d.status === "processing" && <span className="pulse">Indexing…</span>}
                    {ready &&
                      `${d.page_count ? `${d.page_count} pages · ` : ""}${d.chunk_count} passages · ${formatSize(d.size_bytes)}`}
                    {d.status === "failed" && <span className="error">Failed: {d.error}</span>}
                  </span>
                </span>
              </label>
              <button
                className="icon-btn"
                aria-label={`Delete ${d.filename}`}
                onClick={() => {
                  if (window.confirm(`Delete "${d.filename}" and its index entries?`)) onDelete(d.id);
                }}
              >
                ×
              </button>
            </li>
          );
        })}
      </ul>
    </aside>
  );
}
