import { useEffect, useMemo, useState } from "react";
import ShopperPicker from "./components/ShopperPicker.jsx";
import { colourHex } from "./colours.js";
import { loadJson } from "./data.js";
import Moments from "./pages/Moments.jsx";
import Story from "./pages/Story.jsx";
import Swipe from "./pages/Swipe.jsx";

const PAGES = [
  { path: "moments", label: "Moments", hint: "Shop by the moment you're in" },
  { path: "story", label: "Style story", hint: "Your wardrobe, and what comes next" },
  { path: "swipe", label: "Swipe", hint: "Teach it your taste" },
];

function currentPage() {
  const path = window.location.hash.replace(/^#\/?/, "");
  return PAGES.some((p) => p.path === path) ? path : "moments";
}

function savedShopper() {
  try {
    return JSON.parse(localStorage.getItem("kairos-shopper")) ?? null;
  } catch {
    return null;
  }
}

export default function App() {
  const [page, setPage] = useState(currentPage);
  const [shared, setShared] = useState(null);
  const [error, setError] = useState(null);
  const [shopper, setShopper] = useState(savedShopper);

  useEffect(() => {
    const onHash = () => setPage(currentPage());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  useEffect(() => {
    Promise.all([loadJson("customers.json"), loadJson("catalog.json"), loadJson("trending.json")])
      .then(([customers, catalog, trending]) => setShared({ ...customers, catalog, trending }))
      .catch(setError);
  }, []);

  const customer = useMemo(() => {
    if (!shared || shopper?.kind !== "customer") return null;
    return shared.customers.find((c) => c.id === shopper.id) ?? null;
  }, [shared, shopper]);

  // Start as the first real shopper, or fix a saved choice that no longer exists.
  useEffect(() => {
    if (!shared) return;
    const valid = shopper?.kind === "guest" || shared.customers.some((c) => c.id === shopper?.id);
    if (!valid) setShopper({ kind: "customer", id: shared.customers[0].id });
  }, [shared, shopper]);

  useEffect(() => {
    if (!shopper) return;
    try {
      localStorage.setItem("kairos-shopper", JSON.stringify(shopper));
    } catch {
      // Storage can be unavailable (private windows); the choice just won't be remembered.
    }
  }, [shopper]);

  // The site takes its accent colour from the shopper's favourite colour.
  const accent = customer ? colourHex(customer.styleDna.colours[0]?.[0]) : "#b4532a";
  const accentStyle = { "--accent": accent === "#1d1c1a" || accent === "#f7f6f2" ? "#b4532a" : accent };

  if (error) {
    return (
      <main className="page">
        <p className="notice">The shop data could not be loaded: {error.message}</p>
      </main>
    );
  }
  if (!shared || !shopper) return <main className="page loading">Opening the shop…</main>;

  const props = { shared, shopper, customer, setShopper };
  return (
    <div className="app" style={accentStyle}>
      <header className="topbar">
        <a className="wordmark" href="#/moments" aria-label="Kairos home">
          kairos<span className="wordmark-dot">.</span>
        </a>
        <nav className="nav" aria-label="Pages">
          {PAGES.map((p) => (
            <a key={p.path} href={`#/${p.path}`} className={page === p.path ? "active" : ""} title={p.hint}>
              {p.label}
            </a>
          ))}
        </nav>
        <ShopperPicker customers={shared.customers} shopper={shopper} onChange={setShopper} />
      </header>

      {page === "moments" && <Moments {...props} />}
      {page === "story" && <Story {...props} />}
      {page === "swipe" && <Swipe {...props} />}

      <footer className="footer">
        Real recommendations from the two-tower model <strong>{shared.modelVersion}</strong>, trained on the
        H&amp;M dataset up to 15 Sep 2020. The sample shoppers are real customers from the test week
        (16–22 Sep 2020); "really bought" marks what they actually bought that week.
      </footer>
    </div>
  );
}
