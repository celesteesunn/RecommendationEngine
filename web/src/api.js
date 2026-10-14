// The live recommendation API (src/api/ in the repository). The Vite dev server forwards
// /api to it (see vite.config.js). When it is not running, the site uses its saved data files.

const API = `${import.meta.env.BASE_URL}api`;
let health = null;

async function call(path, options) {
  const response = await fetch(`${API}${path}`, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const error = new Error(typeof body.detail === "string" ? body.detail : `The API answered ${response.status}`);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

// A failed connection, or a 5xx from the API or the dev server's proxy, means the API is down.
// A 4xx (unknown customer, bad input) is an answer, not an outage.
export const apiIsDown = (error) => !error.status || error.status >= 500;

// The model version and sizes when the API is up, otherwise null. `again` asks afresh.
export function checkLive(again = false) {
  if (!health || again) {
    health = call("/health", { signal: AbortSignal.timeout(4000) }).catch(() => null);
  }
  return health;
}

export const fetchCustomer = (id) => call(`/customers/${encodeURIComponent(id.trim())}`);
export const fetchRandomCustomer = () => call("/customers/random?warm=true");

// The model's picks for a shopper at a moment. Likes are added to the shopper's history.
// blend "best": a real customer's own recent products first, then the model's; "model": model only.
export function fetchPicks(shopper, moment, { k = 24, history = [], exclude = [], blend = "best" } = {}) {
  const body = { ...moment, k, history, exclude, blend };
  if (shopper.kind === "customer") body.customerId = shopper.customerId ?? shopper.id;
  else body.ageBucket = shopper.age;
  return call("/recommendations", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}

// The catalog starts with the products in the saved data; live answers bring their own details.
export function addProducts(catalog, products) {
  for (const item of products) {
    const { articleId, score, source, ...details } = item;
    if (!catalog[articleId]) catalog[articleId] = details;
  }
}
