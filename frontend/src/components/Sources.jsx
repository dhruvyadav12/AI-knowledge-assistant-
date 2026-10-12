import { api } from "../api.js";

export default function Sources({ sources, active, onActive }) {
  return (
    <ol className="sources" aria-label="Sources">
      {sources.map((s) => {
        const open = active === s.index;
        return (
          <li key={s.index} className={`source ${open ? "open" : ""}`}>
            <button
              className="source-head"
              aria-expanded={open}
              onClick={() => onActive(open ? null : s.index)}
            >
              <span className="source-no">{s.index}</span>
              <span className="source-file" title={s.filename}>{s.filename}</span>
              {s.page && <span className="page-tab">p. {s.page}</span>}
            </button>
            <p className="snippet">
              <mark>{s.snippet}</mark>
            </p>
            {open && (
              <a className="link" href={api.documentUrl(s.document_id, s.page)} target="_blank" rel="noreferrer">
                Open {s.page ? `page ${s.page}` : "document"}
              </a>
            )}
          </li>
        );
      })}
    </ol>
  );
}
