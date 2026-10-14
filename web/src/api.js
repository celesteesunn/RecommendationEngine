// The live recommendation API (src/api/ in the repository). The Vite dev server forwards
// /api to it (see vite.config.js). When it is not running, the site uses its saved data files.

const API = `${import.meta.env.BASE_URL}api`;
let health = null;

async function call(path, options) {
  const response = await fetch(`${API}${path}`, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(typeof body.detail === "string" ? body.detail : `The API answered ${response.status}`);
  }
  return response.json();
}

// The model version and sizes when the API is up, otherwise null. Asked once per page load.
export function checkLive() {
  if (!health) {
    health = call("/health", { signal: AbortSignal.timeout(4000) }).catch(() => null);
  }
  return health;
}

export const fetchCustomer = (id) => call(`/customers/${encodeURIComponent(id.trim())}`);
export const fetchRandomCustomer = () => call("/customers/random?warm=true");

// The model's picks for a shopper at a moment. Likes are added to the shopper's history.
export function fetchPicks(shopper, moment, { k = 24, history = [], exclude = [] } = {}) {
  const body = { ...moment, k, history, exclude };
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
    const { articleId, score, ...details } = item;
    if (!catalog[articleId]) catalog[articleId] = details;
  }
}
