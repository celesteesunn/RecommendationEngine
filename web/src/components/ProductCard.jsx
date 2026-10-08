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

export default function ProductCard({ id, item, rank, reasons = [], bought = false, fresh = false }) {
  if (!item) return null;
  return (
    <article className={`card${bought ? " card-bought" : ""}${fresh ? " card-fresh" : ""}`}>
      <div className="card-media">
        <ProductVisual id={id} item={item} />
        {rank != null && <span className="card-rank">{rank}</span>}
        {bought && <span className="stamp">Really bought</span>}
      </div>
      <div className="card-body">
        <h3 className="card-name">{item.name}</h3>
        <p className="card-meta">
          {item.colour} · {item.type}
          <PriceDots band={item.priceBand} />
        </p>
        {reasons.length > 0 && (
          <ul className="reasons">
            {reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        )}
      </div>
    </article>
  );
}
