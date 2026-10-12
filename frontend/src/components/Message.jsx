import { useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import Sources from "./Sources.jsx";

export default function Message({ message }) {
  const { role, content, sources, streaming, error } = message;
  const [active, setActive] = useState(null);

  // Turn [1] style citations into clickable markers, but only for sources that exist.
  const markdown = useMemo(() => {
    if (!sources?.length) return content;
    const valid = new Set(sources.map((s) => s.index));
    return content.replace(/\[(\d+)\]/g, (whole, n) => (valid.has(Number(n)) ? `[${n}](cite:${n})` : whole));
  }, [content, sources]);

  if (role === "user") {
    return (
      <div className="msg user">
        <p>{content}</p>
      </div>
    );
  }

  return (
    <div className="msg assistant">
      {streaming && !content && !error && <p className="pulse muted">Searching your documents…</p>}

      {content && (
        <div className="answer">
          <ReactMarkdown
            urlTransform={(url) => url}
            components={{
              a: ({ href, children }) =>
                href?.startsWith("cite:") ? (
                  <button
                    className="cite"
                    onClick={() => setActive(Number(href.slice(5)))}
                    aria-label={`Show source ${href.slice(5)}`}
                  >
                    {children}
                  </button>
                ) : (
                  <a href={href} target="_blank" rel="noreferrer">{children}</a>
                ),
            }}
          >
            {markdown}
          </ReactMarkdown>
        </div>
      )}

      {error && <p className="error" role="alert">{error}</p>}

      {sources?.length > 0 && <Sources sources={sources} active={active} onActive={setActive} />}
    </div>
  );
}
