import { useState } from "react";
import { colourHex, inkFor } from "../colours.js";
import { imageUrl } from "../data.js";

// Price bands 0-9 from the features become one to five dots.
function PriceDots({ band }) {
  if (band < 0) return null;
  const filled = Math.floor(band / 2) + 1;
  return (
    <span className="price" title={`Price band ${band + 1} of 10`} aria-label={`Price band ${band + 1} of 10`}>
      {"●".repeat(filled)}
      <span className="price-empty">{"●".repeat(5 - filled)}</span>
    </span>
  );
}

// The real photo when it was downloaded, otherwise a card in the product's own colour.
export function ProductVisual({ id, item, size = "large" }) {
  const [failed, setFailed] = useState(false);
  const hex = colourHex(item.colour);
  if (!failed) {
    return (
      <div className={`visual visual-${size}`} style={{ background: hex }}>
        <img src={imageUrl(id)} alt={item.name} loading="lazy" onError={() => setFailed(true)} />
      </div>
    );
  }
  return (
    <div className={`visual visual-${size} swatch`} style={{ background: hex, color: inkFor(hex) }}>
      <span className="swatch-type">{item.type}</span>
      <span className="swatch-colour">{item.colour}</span>
    </div>
  );
}

const SOURCES = { model: "Model pick", "bought before": "↻ Bought before" };

// source: where the pick came from ("model" or "bought before"); reasons: patterns it matches.
export default function ProductCard({ id, item, rank, reasons = [], bought = false, fresh = false, source }) {
  if (!item) return null;
  const tags = source === "bought before" ? reasons.filter((r) => r !== "You bought this before") : reasons;
  return (
    <article className={`card${bought ? " card-bought" : ""}${fresh ? " card-fresh" : ""}`}>
      <div className="card-media">
        <ProductVisual id={id} item={item} />
        {rank != null && <span className="card-rank">{rank}</span>}
        {bought && <span className="stamp">Really bought</span>}
      </div>
      <div className="card-body">
        {source && <p className={`card-source source-${source === "model" ? "model" : "own"}`}>{SOURCES[source]}</p>}
        <h3 className="card-name">{item.name}</h3>
        <p className="card-meta">
          {item.colour} · {item.type}
          <PriceDots band={item.priceBand} />
        </p>
        {tags.length > 0 && (
          <ul className="reasons" title="Patterns in the shopper's data that this pick matches">
            {tags.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        )}
      </div>
    </article>
  );
}
