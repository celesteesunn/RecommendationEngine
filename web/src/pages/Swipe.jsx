import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ProductVisual } from "../components/ProductCard.jsx";
import { loadJson, swipeStartKey } from "../data.js";

// How far one swipe moves the shopper's vector, relative to its length.
const LIKE_STEP = 0.45;
const PASS_STEP = 0.15;
const DRAG_THRESHOLD = 110;
const FEED_SIZE = 6;

const dot = (a, b) => a.reduce((sum, x, i) => sum + x * b[i], 0);
const norm = (a) => Math.sqrt(dot(a, a));
const cosine = (a, b) => dot(a, b) / (norm(a) * norm(b) || 1);

function nudge(query, vector, step) {
  const scale = (step * norm(query)) / (norm(vector) || 1);
  return query.map((x, i) => x + scale * vector[i]);
}

export default function Swipe({ shared, shopper }) {
  const [pool, setPool] = useState(null);
  const [query, setQuery] = useState(null);
  const [seen, setSeen] = useState(() => new Set());
  const [liked, setLiked] = useState([]);
  const [passed, setPassed] = useState(0);
  const [drag, setDrag] = useState(0);
  const [leaving, setLeaving] = useState(null);
  const start = useRef(null);
  const previousRanks = useRef(new Map());

  const reset = useCallback(() => {
    if (!pool) return;
    setQuery(pool.start[swipeStartKey(shopper)]);
    setSeen(new Set());
    setLiked([]);
    setPassed(0);
    previousRanks.current = new Map();
  }, [pool, shopper]);

  useEffect(() => {
    loadJson("swipe.json").then(setPool);
  }, []);
  useEffect(reset, [reset]);

  const ranking = useMemo(() => {
    if (!pool || !query) return [];
    return pool.items
      .map((id, i) => ({ id, score: dot(query, pool.vectors[i]), vector: pool.vectors[i] }))
      .filter((entry) => !seen.has(entry.id))
      .sort((a, b) => b.score - a.score);
  }, [pool, query, seen]);

  const current = ranking[0];
  const feed = ranking.slice(1, FEED_SIZE + 1);
  const learned = pool && query ? Math.min(100, Math.round(((1 - cosine(query, pool.start[swipeStartKey(shopper)])) / 0.35) * 100)) : 0;

  const decide = useCallback(
    (like) => {
      if (!current || leaving) return;
      previousRanks.current = new Map(ranking.map((entry, i) => [entry.id, i]));
      setLeaving(like ? "right" : "left");
      setTimeout(() => {
        setQuery((q) => nudge(q, current.vector, like ? LIKE_STEP : -PASS_STEP));
        setSeen((s) => new Set(s).add(current.id));
        if (like) setLiked((l) => [current.id, ...l]);
        else setPassed((n) => n + 1);
        setLeaving(null);
        setDrag(0);
      }, 220);
    },
    [current, leaving, ranking],
  );

  useEffect(() => {
    const onKey = (event) => {
      if (event.key === "ArrowRight") decide(true);
      if (event.key === "ArrowLeft") decide(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [decide]);

  function onPointerDown(event) {
    start.current = event.clientX;
    event.currentTarget.setPointerCapture(event.pointerId);
  }
  function onPointerMove(event) {
    if (start.current != null) setDrag(event.clientX - start.current);
  }
  function onPointerUp() {
    if (start.current == null) return;
    start.current = null;
    if (drag > DRAG_THRESHOLD) decide(true);
    else if (drag < -DRAG_THRESHOLD) decide(false);
    else setDrag(0);
  }

  if (!pool || !query) return <main className="page loading">Shuffling the deck…</main>;

  const item = current && shared.catalog[current.id];
  const offset = leaving === "right" ? 600 : leaving === "left" ? -600 : drag;

  return (
    <main className="page swipe-page">
      <section className="hero">
        <p className="eyebrow">Swipe to teach</p>
        <h1 className="headline">No search box. Show it what you like.</h1>
        <p className="lede">
          Every product here has a vector from the model, and so do you. A like pulls your vector towards the
          product, a pass pushes it away, and all {pool.items.length} products are re-ranked on the spot.
        </p>
      </section>

      <div className="swipe-layout">
        <div className="deck">
          {current ? (
            <article
              className={`swipe-card${drag > 40 ? " leaning-like" : drag < -40 ? " leaning-pass" : ""}`}
              style={{ transform: `translateX(${offset}px) rotate(${offset / 18}deg)`, transition: start.current != null ? "none" : undefined }}
              onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={onPointerUp} onPointerCancel={onPointerUp}
            >
              <ProductVisual id={current.id} item={item} />
              <div className="swipe-info">
                <h2>{item.name}</h2>
                <p>{item.colour} · {item.type} · {item.index}</p>
              </div>
              <span className="swipe-badge like">Like</span>
              <span className="swipe-badge pass">Pass</span>
            </article>
          ) : (
            <p className="notice">You've seen the whole deck. Start again to teach it something new.</p>
          )}
          <div className="swipe-buttons">
            <button type="button" className="round pass" onClick={() => decide(false)} aria-label="Pass">✕</button>
            <button type="button" className="round like" onClick={() => decide(true)} aria-label="Like">♥</button>
          </div>
          <p className="muted small">Drag the card, or use ← and → on your keyboard.</p>
        </div>

        <aside className="learning">
          <h2 className="section-title">Taste learned</h2>
          <div className="meter" role="meter" aria-valuenow={learned} aria-valuemin={0} aria-valuemax={100}>
            <span style={{ width: `${learned}%` }} />
          </div>
          <p className="muted small">
            {liked.length} liked · {passed} passed · your vector has moved {learned}% of the way to a new taste.
          </p>

          <h3 className="section-title small-title">Your feed right now</h3>
          <ol className="live-feed">
            {feed.map((entry, i) => {
              const before = previousRanks.current.get(entry.id);
              const moved = before == null ? 0 : before - (i + 1);
              const feedItem = shared.catalog[entry.id];
              return (
                <li key={entry.id}>
                  <ProductVisual id={entry.id} item={feedItem} size="small" />
                  <span className="feed-name">{feedItem.name}</span>
                  <span className={`move${moved > 0 ? " up" : moved < 0 ? " down" : ""}`}>
                    {moved > 0 ? `▲${moved}` : moved < 0 ? `▼${-moved}` : "·"}
                  </span>
                </li>
              );
            })}
          </ol>

          {liked.length > 0 && (
            <>
              <h3 className="section-title small-title">Liked</h3>
              <div className="liked-tray">
                {liked.map((id) => (
                  <div key={id} className="liked-item" title={shared.catalog[id].name}>
                    <ProductVisual id={id} item={shared.catalog[id]} size="small" />
                  </div>
                ))}
              </div>
            </>
          )}
          <button type="button" className="chip" onClick={reset}>Start again</button>
        </aside>
      </div>
    </main>
  );
}
