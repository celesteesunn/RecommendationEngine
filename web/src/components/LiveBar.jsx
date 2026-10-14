import { useState } from "react";
import { fetchCustomer, fetchRandomCustomer } from "../api.js";

// Shows whether picks come live from the model, and lets anyone shop as any real customer.
export default function LiveBar({ live, onCustomer }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState(null);

  if (!live) {
    return (
      <p className="livebar livebar-off">
        <span className="live-dot" aria-hidden="true" />
        Saved picks for 19 sample shoppers. Start the API (<code>uvicorn src.api.main:app</code>) for live picks for
        any customer.
      </p>
    );
  }

  async function open(load) {
    setBusy(true);
    setProblem(null);
    try {
      onCustomer(await load());
      setText("");
    } catch (error) {
      setProblem(error.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="livebar">
      <p className="livebar-status">
        <span className="live-dot on" aria-hidden="true" />
        <strong>Live</strong>: model {live.modelVersion} is answering for {live.customers.toLocaleString("en-GB")} customers
        and {live.products.toLocaleString("en-GB")} products.
      </p>
      <form className="livebar-find" onSubmit={(e) => { e.preventDefault(); if (text.trim()) open(() => fetchCustomer(text)); }}>
        <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Any customer ID (8+ characters)"
          aria-label="Customer ID" spellCheck="false" />
        <button type="submit" className="chip" disabled={busy || !text.trim()}>Find</button>
        <button type="button" className="chip chip-accent" disabled={busy} onClick={() => open(fetchRandomCustomer)}
          title="A random real customer from the test week, so you can check what they really bought">
          Surprise me
        </button>
      </form>
      {problem && <p className="livebar-problem" role="alert">{problem}</p>}
    </div>
  );
}
