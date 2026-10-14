import { useCallback, useEffect, useMemo, useState } from "react";
import { checkLive, fetchCustomer } from "./api.js";
import LiveBar from "./components/LiveBar.jsx";
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
  // undefined while checking, then the API's summary, or null when it is not running.
  const [live, setLive] = useState(undefined);
  // Real customers looked up through the API, by their short ID.
  const [looked, setLooked] = useState({});

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

  useEffect(() => {
    checkLive().then(setLive);
  }, []);

  const remember = useCallback(
    (profile) => {
      for (const [id, details] of Object.entries(profile.products)) shared.catalog[id] ??= details;
      setLooked((all) => ({ ...all, [profile.id]: profile }));
      return profile;
    },
    [shared],
  );
  const openCustomer = useCallback(
    (profile) => {
      remember(profile);
      setShopper({ kind: "customer", id: profile.id, customerId: profile.customerId });
    },
    [remember],
  );

  const customer = useMemo(() => {
    if (!shared || shopper?.kind !== "customer") return null;
    return shared.customers.find((c) => c.id === shopper.id) ?? looked[shopper.id] ?? null;
  }, [shared, shopper, looked]);

  // Start as the first sample shopper. A customer looked up live is fetched again after a
  // reload; without the API, a saved choice that is not a sample falls back to the first one.
  useEffect(() => {
    if (!shared || live === undefined) return;
    const first = { kind: "customer", id: shared.customers[0].id };
    if (!shopper) return setShopper(first);
    if (shopper.kind === "guest" || customer) return;
    if (live && shopper.customerId) {
      fetchCustomer(shopper.customerId).then(remember).catch(() => setShopper(first));
    } else {
      setShopper(first);
    }
  }, [shared, live, shopper, customer, remember]);

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
  if (!shared || !shopper || live === undefined || (shopper.kind === "customer" && !customer)) {
    return <main className="page loading">Opening the shop…</main>;
  }

  const props = { shared, shopper, customer, setShopper, live };
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
        <ShopperPicker customers={shared.customers} looked={Object.values(looked)} shopper={shopper} onChange={setShopper} />
      </header>
      <LiveBar live={live} onCustomer={openCustomer} />

      {page === "moments" && <Moments {...props} />}
      {page === "story" && <Story {...props} />}
      {page === "swipe" && <Swipe {...props} />}

      <footer className="footer">
        Real recommendations from the two-tower model <strong>{live?.modelVersion ?? shared.modelVersion}</strong>,
        trained on the H&amp;M dataset up to 15 Sep 2020
        {live ? ", computed live by the API for every change you make" : ", saved for the sample shoppers"}. Customers
        from the test week (16–22 Sep 2020) show "really bought" for what they actually bought that week.
      </footer>
    </div>
  );
}
