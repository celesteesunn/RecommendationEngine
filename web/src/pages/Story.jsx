import { useEffect, useMemo, useRef, useState } from "react";
import { addProducts, fetchPicks } from "../api.js";
import ProductCard, { ProductVisual } from "../components/ProductCard.jsx";
import { colourHex, inkFor } from "../colours.js";
import { CHANNELS, DAYS, MONTHS, formatDate, loadJson, parseMoment } from "../data.js";
import { reasonsFor, shopperFacts } from "../reasons.js";

const PER_MONTH = 6;
// Customers outside the test week have no known next visit: show a Wednesday in September, online.
const DEFAULT_NEXT = "d4-m9-c2";

function monthLabel(key) {
  const [year, month] = key.split("-").map(Number);
  return `${MONTHS[month - 1].slice(0, 3)} ${year}`;
}

function StyleDna({ dna }) {
  const other = 1 - dna.colours.reduce((sum, [, share]) => sum + share, 0);
  const segments = other > 0.005 ? [...dna.colours, ["Other colours", other]] : dna.colours;
  return (
    <div className="dna">
      <h2 className="section-title">Style DNA</h2>
      <div className="dna-bar" role="img" aria-label="Share of colours bought">
        {segments.map(([name, share]) => {
          const hex = name === "Other colours" ? "#e4ddcf" : colourHex(name);
          return (
            <span key={name} style={{ flexGrow: share, background: hex, color: inkFor(hex) }} title={`${name}: ${Math.round(share * 100)}%`}>
              {share >= 0.08 ? `${name} ${Math.round(share * 100)}%` : ""}
            </span>
          );
        })}
      </div>
      <ul className="dna-types">
        {dna.types.map(([name, share]) => (
          <li key={name}>
            <span className="dna-type-bar" style={{ width: `${Math.max(share * 100 * 2.5, 6)}%` }} />
            <span>{name}</span>
            <span className="muted">{Math.round(share * 100)}%</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function Story({ shared, shopper, customer, setShopper, live }) {
  const [next, setNext] = useState(null);
  const [reveal, setReveal] = useState(false);
  const timeline = useRef(null);
  const nextKey = customer?.nextVisit?.moment ?? DEFAULT_NEXT;

  useEffect(() => {
    setReveal(false);
    setNext(null);
    if (!customer) return undefined;
    let current = true;
    const picks = live
      ? fetchPicks(shopper, parseMoment(nextKey), { k: 12 }).then((answer) => {
          addProducts(shared.catalog, answer.items);
          return answer.items.map((item) => item.articleId);
        })
      : loadJson(`moments/${customer.id}.json`).then((table) => table[nextKey].slice(0, 12));
    picks.then((ids) => current && setNext(ids)).catch(() => current && setNext([]));
    return () => {
      current = false;
    };
  }, [customer, live]);

  const months = useMemo(() => {
    if (!customer) return [];
    const groups = new Map();
    for (const p of customer.purchases) {
      const key = p.date.slice(0, 7);
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(p);
    }
    return [...groups.entries()];
  }, [customer]);

  // Open the timeline at the most recent purchases.
  useEffect(() => {
    if (timeline.current) timeline.current.scrollLeft = timeline.current.scrollWidth;
  }, [months]);

  const facts = useMemo(() => shopperFacts(customer), [customer]);

  if (!customer) {
    return (
      <main className="page">
        <section className="hero">
          <p className="eyebrow">Style story</p>
          <h1 className="headline">A new visitor has no story yet.</h1>
          <p className="lede">Every purchase writes a chapter. Pick one of the real shoppers to read theirs:</p>
          <div className="presets">
            {shared.customers.filter((c) => c.warm).slice(0, 6).map((c) => (
              <button key={c.id} type="button" className="chip" onClick={() => setShopper({ kind: "customer", id: c.id })}>
                Shopper {c.id} · {c.ageBucket}
              </button>
            ))}
          </div>
        </section>
      </main>
    );
  }

  const moment = parseMoment(nextKey);
  const bought = new Set(customer.boughtInTestWeek);
  const first = customer.purchases[0];
  const last = customer.purchases[customer.purchases.length - 1];
  // Live profiles carry only the 12 weeks the model learned from; the samples carry everything.
  const isSample = shared.customers.some((c) => c.id === customer.id);

  return (
    <main className="page">
      <section className="hero story-hero">
        <div>
          <p className="eyebrow">Style story · Shopper {customer.id}</p>
          <h1 className="headline">
            {first
              ? `${customer.purchases.length} pieces ${isSample ? `since ${formatDate(first.date)}` : "in the 12 weeks before 16 Sep 2020"}.`
              : "No purchases in the 12 weeks the model learned from."}
          </h1>
          <p className="lede">
            Aged {customer.ageBucket}, club member status {customer.club.toLowerCase()}, shops online{" "}
            {Math.round(customer.onlineShare * 100)}% of the time.{last && ` Last bought on ${formatDate(last.date)}.`}
          </p>
        </div>
        <StyleDna dna={customer.styleDna} />
      </section>

      <section>
        <h2 className="section-title">The story so far</h2>
        <div className="timeline" ref={timeline}>
          {months.map(([key, purchases]) => (
            <div key={key} className="timeline-month">
              <span className="timeline-label">{monthLabel(key)}</span>
              <div className="timeline-items">
                {purchases.slice(0, PER_MONTH).map((p, i) => (
                  <div key={`${p.article_id}-${i}`} className="timeline-item" title={`${shared.catalog[p.article_id].name} · ${formatDate(p.date)}`}>
                    <ProductVisual id={p.article_id} item={shared.catalog[p.article_id]} size="small" />
                  </div>
                ))}
                {purchases.length > PER_MONTH && <span className="timeline-more">+{purchases.length - PER_MONTH}</span>}
              </div>
            </div>
          ))}
          <div className="timeline-month timeline-next">
            <span className="timeline-label">Next</span>
            <span className="timeline-next-text">
              {customer.nextVisit
                ? `${DAYS[moment.day - 1]}, ${formatDate(customer.nextVisit.date)}, ${CHANNELS[moment.channel]}`
                : "Not in the test week"}
            </span>
          </div>
        </div>
      </section>

      <section className="feed-head">
        <h2 className="section-title">The next chapter</h2>
        {bought.size > 0 && (
          <label className="switch">
            <input type="checkbox" checked={reveal} onChange={(e) => setReveal(e.target.checked)} />
            <span>Reveal what they really bought</span>
          </label>
        )}
      </section>
      <p className="lede">
        {customer.nextVisit
          ? `What the model expected for their next visit on ${DAYS[moment.day - 1]} ${formatDate(customer.nextVisit.date)}, ${CHANNELS[moment.channel]}.`
          : `They did not shop in the test week, so this is what the model would pick for a ${DAYS[moment.day - 1]} in ${MONTHS[moment.month - 1]}, ${CHANNELS[moment.channel]}.`}
      </p>
      {reveal && (
        <p className="reveal-note">
          They really bought {customer.boughtInTestWeek.length}{" "}
          {customer.boughtInTestWeek.length === 1 ? "product that week; it is" : "products that week;"}{" "}
          {customer.boughtInTestWeek.length === 1
            ? (next.includes(customer.boughtInTestWeek[0]) ? "" : "not ")
            : `${next.filter((id) => bought.has(id)).length} of them are `}
          in these 12 picks.
        </p>
      )}
      {!next ? (
        <p className="loading">Writing the next chapter…</p>
      ) : (
        <div className="grid">
          {next.map((id, i) => (
            <ProductCard key={id} id={id} rank={i + 1} item={shared.catalog[id]} bought={reveal && bought.has(id)}
              reasons={reasonsFor(id, shared.catalog[id], facts, shared.trending, moment)} />
          ))}
        </div>
      )}
    </main>
  );
}
