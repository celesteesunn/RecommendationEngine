import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { addProducts, fetchPicks } from "../api.js";
import { ProductVisual } from "../components/ProductCard.jsx";
import { loadJson, swipeStartKey } from "../data.js";

// How far one swipe moves the shopper's vector, relative to its length.
const LIKE_STEP = 0.45;
const PASS_STEP = 0.15;
const DRAG_THRESHOLD = 110;
const FEED_SIZE = 6;
// Live mode: the moment the deck is ranked for, and how many picks to ask for each time.
const LIVE_MOMENT = { day: 4, month: 9, channel: 2 };
const LIVE_K = 30;
const TOP = 24;

const dot = (a, b) => a.reduce((sum, x, i) => sum + x * b[i], 0);
const norm = (a) => Math.sqrt(dot(a, a));
const cosine = (a, b) => dot(a, b) / (norm(a) * norm(b) || 1);

function nudge(query, vector, step) {
  const scale = (step * norm(query)) / (norm(vector) || 1);
  return query.map((x, i) => x + scale * vector[i]);
}

export default function Swipe({ shared, shopper, live }) {
  // Saved mode: a pool of products with vectors, re-ranked in the browser.
  const [pool, setPool] = useState(null);
  const [query, setQuery] = useState(null);
  // Live mode: the model's latest picks, asked again after every swipe.
  const [liveItems, setLiveItems] = useState(null);
  const [problem, setProblem] = useState(null);
  const startTop = useRef(null);
  const [seen, setSeen] = useState(() => new Set());
  const [liked, setLiked] = useState([]);
  const [passed, setPassed] = useState(0);
  const [drag, setDrag] = useState(0);
  const [leaving, setLeaving] = useState(null);
  const start = useRef(null);
  const previousRanks = useRef(new Map());

  const reset = useCallback(() => {
    if (!live && !pool) return;
    if (!live) setQuery(pool.start[swipeStartKey(shopper)]);
    startTop.current = null;
    setLiveItems(null);
    setSeen(new Set());
    setLiked([]);
    setPassed(0);
    previousRanks.current = new Map();
  }, [live, pool, shopper]);

  useEffect(() => {
    if (!live) loadJson("swipe.json").then(setPool);
  }, [live]);
  useEffect(reset, [reset]);

  // Live: likes become the newest part of the shopper's history; everything seen is left out.
  useEffect(() => {
    if (!live) return undefined;
    let current = true;
    setProblem(null);
    fetchPicks(shopper, LIVE_MOMENT, { k: LIVE_K, history: [...liked].reverse(), exclude: [...seen] })
      .then((answer) => {
        if (!current) return;
        addProducts(shared.catalog, answer.items);
        const ids = answer.items.map((item) => item.articleId);
        startTop.current ??= ids.slice(0, TOP);
        setLiveItems(ids);
      })
      .catch((error) => current && setProblem(error.message));
    return () => {
      current = false;
    };
  }, [live, shopper, liked, seen]);

  const ranking = useMemo(() => {
    // Until the next answer arrives, the previous picks minus the one just swiped.
    if (live) return (liveItems ?? []).filter((id) => !seen.has(id)).map((id) => ({ id }));
    if (!pool || !query) return [];
    return pool.items
      .map((id, i) => ({ id, score: dot(query, pool.vectors[i]), vector: pool.vectors[i] }))
      .filter((entry) => !seen.has(entry.id))
      .sort((a, b) => b.score - a.score);
  }, [live, liveItems, pool, query, seen]);

  const current = ranking[0];
  const feed = ranking.slice(1, FEED_SIZE + 1);
  let learned = 0;
  if (live && startTop.current && liveItems) {
    const kept = liveItems.slice(0, TOP).filter((id) => startTop.current.includes(id)).length;
    learned = Math.round(100 * (1 - kept / startTop.current.length));
  } else if (!live && pool && query) {
    learned = Math.min(100, Math.round(((1 - cosine(query, pool.start[swipeStartKey(shopper)])) / 0.35) * 100));
  }

  const decide = useCallback(
    (like) => {
      if (!current || leaving) return;
      previousRanks.current = new Map(ranking.map((entry, i) => [entry.id, i]));
      setLeaving(like ? "right" : "left");
      setTimeout(() => {
        if (!live) setQuery((q) => nudge(q, current.vector, like ? LIKE_STEP : -PASS_STEP));
        setSeen((s) => new Set(s).add(current.id));
        if (like) setLiked((l) => [current.id, ...l]);
        else setPassed((n) => n + 1);
        setLeaving(null);
        setDrag(0);
      }, 220);
    },
    [current, leaving, ranking, live],
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

  if (problem) return <main className="page notice">The model could not be reached: {problem}</main>;
  if (live ? !liveItems : !pool || !query) return <main className="page loading">Shuffling the deck…</main>;

  const item = current && shared.catalog[current.id];
  const offset = leaving === "right" ? 600 : leaving === "left" ? -600 : drag;

  return (
    <main className="page swipe-page">
      <section className="hero">
        <p className="eyebrow">Swipe to teach</p>
        <h1 className="headline">No search box. Show it what you like.</h1>
        {live ? (
          <p className="lede">
            Every like joins your shopping history, and the live model re-ranks all {live.products.toLocaleString("en-GB")}{" "}
            products on sale after each swipe. It predicts what you would buy next, so liking a dress can bring the
            cardigan that goes with it, not just more dresses.
          </p>
        ) : (
          <p className="lede">
            Every product here has a vector from the model, and so do you. A like pulls your vector towards the
            product, a pass pushes it away, and all {pool.items.length} products are re-ranked on the spot.
          </p>
        )}
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
            {liked.length} liked · {passed} passed ·{" "}
            {live ? `${learned}% of your top ${TOP} has changed since you started.` : `your vector has moved ${learned}% of the way to a new taste.`}
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
