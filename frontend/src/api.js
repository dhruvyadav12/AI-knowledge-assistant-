const BASE = "/api";

async function request(path, options) {
  const res = await fetch(BASE + path, options);
  if (!res.ok) {
    let detail;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : null;
    } catch {
      /* non-JSON error body */
    }
    throw new Error(detail || `Request failed (${res.status})`);
  }
  return res.status === 204 ? null : res.json();
}

export const api = {
  health: () => request("/health"),

  listDocuments: () => request("/documents"),
  uploadDocuments: (files) => {
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    return request("/documents", { method: "POST", body: form });
  },
  deleteDocument: (id) => request(`/documents/${id}`, { method: "DELETE" }),
  documentUrl: (id, page) => `${BASE}/documents/${id}/file${page ? `#page=${page}` : ""}`,

  listConversations: () => request("/conversations"),
  createConversation: () => request("/conversations", { method: "POST" }),
  getConversation: (id) => request(`/conversations/${id}`),
  deleteConversation: (id) => request(`/conversations/${id}`, { method: "DELETE" }),
};

/**
 * Ask a question and consume the Server-Sent Events stream.
 * handlers: { onSources(list), onToken(text), onDone(), onError(message) }
 */
export async function streamAnswer(conversationId, body, handlers, signal) {
  const res = await fetch(`${BASE}/conversations/${conversationId}/messages/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok || !res.body) throw new Error(`Request failed (${res.status})`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const dispatch = (event, data) => {
    if (event === "sources") handlers.onSources?.(data.sources);
    else if (event === "token") handlers.onToken?.(data.text);
    else if (event === "done") handlers.onDone?.(data);
    else if (event === "error") handlers.onError?.(data.detail);
  };

  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let split;
    while ((split = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, split);
      buffer = buffer.slice(split + 2);
      const event = /^event: (.*)$/m.exec(block)?.[1];
      const data = /^data: (.*)$/m.exec(block)?.[1];
      if (event && data) dispatch(event, JSON.parse(data));
    }
  }
}
