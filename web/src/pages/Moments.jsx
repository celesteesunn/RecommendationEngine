import { useEffect, useMemo, useRef, useState } from "react";
import ProductCard from "../components/ProductCard.jsx";
import { CHANNELS, DAYS, MONTHS, formatDate, loadJson, momentKey, parseMoment, recommendationsFile, season } from "../data.js";
import { reasonsFor, shopperFacts } from "../reasons.js";

const PRESETS = [
  { label: "Lazy Sunday, online", moment: { day: 1, month: 3, channel: 2 } },
  { label: "Summer Saturday in town", moment: { day: 7, month: 7, channel: 1 } },
  { label: "Back to work, September", moment: { day: 2, month: 9, channel: 2 } },
  { label: "December weekend", moment: { day: 7, month: 12, channel: 1 } },
];
const DEFAULT_MOMENT = { day: 4, month: 9, channel: 2 };
const SHOWN = 12;
const REVEAL_SHOWN = 24;

function InlineSelect({ value, options, onChange, label }) {
  return (
    <select className="inline-select" aria-label={label} value={value} onChange={(e) => onChange(Number(e.target.value))}>
      {options.map(([v, text]) => (
        <option key={v} value={v}>
          {text}
        </option>
      ))}
    </select>
  );
}

export default function Moments({ shared, shopper, customer }) {
  const realMoment = customer ? parseMoment(customer.nextVisit.moment) : null;
  const [moment, setMoment] = useState(realMoment ?? DEFAULT_MOMENT);
  const [table, setTable] = useState(null);
  const [reveal, setReveal] = useState(false);
  // The picks shown for the previous moment, to highlight what changed.
  const previous = useRef({ key: null, picks: [] });

  // A new shopper starts at the moment they really shopped (or a Wednesday in September).
  useEffect(() => {
    setMoment(realMoment ?? DEFAULT_MOMENT);
    setReveal(false);
    previous.current = { key: null, picks: [] };
    setTable(null);
    loadJson(recommendationsFile(shopper)).then(setTable);
  }, [shopper.kind, shopper.id, shopper.age]);

  // Revealing shows the full top 24, so every real purchase the model found is visible.
  const shown = reveal ? REVEAL_SHOWN : SHOWN;
  const picks = useMemo(() => (table ? table[momentKey(moment)].slice(0, shown) : []), [table, moment, shown]);
  const key = momentKey(moment);
  const fresh = useMemo(() => {
    const before = previous.current;
    if (!before.key || before.key === key) return new Set();
    return new Set(picks.filter((id) => !before.picks.includes(id)));
  }, [picks, key]);
  useEffect(() => {
    if (picks.length) previous.current = { key, picks };
  }, [picks, key]);

  const facts = useMemo(() => shopperFacts(customer), [customer]);
  const bought = new Set(customer?.boughtInTestWeek ?? []);
  const fullList = table ? table[momentKey(moment)] : [];
  const hits = fullList.filter((id) => bought.has(id)).length;
  const isRealMoment = realMoment && momentKey(realMoment) === momentKey(moment);
  const update = (field) => (value) => setMoment((m) => ({ ...m, [field]: value }));

  return (
    <main className="page">
      <section className="hero">
        <p className="eyebrow">No aisles. No categories. Just the moment you're in.</p>
        <h1 className="sentence">
          It's a{" "}
          <InlineSelect label="Day" value={moment.day} onChange={update("day")} options={DAYS.map((d, i) => [i + 1, d])} />{" "}
          in{" "}
          <InlineSelect label="Month" value={moment.month} onChange={update("month")} options={MONTHS.map((m, i) => [i + 1, m])} />
          , and I'm shopping{" "}
          <InlineSelect label="Channel" value={moment.channel} onChange={update("channel")}
            options={Object.entries(CHANNELS).map(([v, t]) => [Number(v), t])} />
          .
        </h1>

        <div className="year-ring" role="group" aria-label="Month">
          {MONTHS.map((name, i) => (
            <button key={name} type="button" className={`ring-month ring-${season(i + 1)}${moment.month === i + 1 ? " on" : ""}`}
              onClick={() => update("month")(i + 1)} aria-pressed={moment.month === i + 1} title={name}>
              {name.slice(0, 3)}
            </button>
          ))}
        </div>

        <div className="presets">
          {PRESETS.map((p) => (
            <button key={p.label} type="button" className="chip" onClick={() => setMoment(p.moment)}>
              {p.label}
            </button>
          ))}
          {realMoment && !isRealMoment && (
            <button type="button" className="chip chip-accent" onClick={() => setMoment(realMoment)}>
              ↺ The moment they really shopped
            </button>
          )}
        </div>
      </section>

      <section className="feed-head">
        <p>
          {fresh.size > 0 ? (
            <><strong>{fresh.size} new picks</strong> for this moment. </>
          ) : (
            <>Top {shown} picks for this moment. </>
          )}
          {isRealMoment && <span className="tag">This is when they really shopped: {formatDate(customer.nextVisit.date)}</span>}
        </p>
        {customer && (
          <label className="switch">
            <input type="checkbox" checked={reveal} onChange={(e) => setReveal(e.target.checked)} />
            <span>Reveal what they really bought</span>
          </label>
        )}
      </section>

      {reveal && customer && (
        <p className="reveal-note">
          {hits > 0
            ? `${hits} of the ${customer.boughtInTestWeek.length} products this shopper really bought that week ${hits === 1 ? "is" : "are"} in the model's top ${fullList.length} for this moment, marked below.`
            : `None of the ${customer.boughtInTestWeek.length} products they really bought are in the top ${fullList.length} for this moment. Try the moment they really shopped.`}
        </p>
      )}

      {!table ? (
        <p className="loading">Finding picks…</p>
      ) : (
        <div className="grid">
          {picks.map((id, i) => (
            <ProductCard key={id} id={id} rank={i + 1} item={shared.catalog[id]} fresh={fresh.has(id)}
              bought={reveal && bought.has(id)}
              reasons={reasonsFor(id, shared.catalog[id], facts, shared.trending, moment, shopper.age)} />
          ))}
        </div>
      )}
    </main>
  );
}
