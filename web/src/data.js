// Loading the static data exported by src/serving/site_data.py, and small shared helpers.

const BASE = import.meta.env.BASE_URL;
const cache = new Map();

export function loadJson(path) {
  if (!cache.has(path)) {
    cache.set(
      path,
      fetch(`${BASE}data/${path}`).then((response) => {
        if (!response.ok) throw new Error(`Could not load ${path} (${response.status})`);
        return response.json();
      }),
    );
  }
  return cache.get(path);
}

export const imageUrl = (articleId) => `${BASE}images/${articleId}.jpg`;

// Day numbers follow the training data: 1 = Sunday ... 7 = Saturday.
export const DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
export const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];
export const CHANNELS = { 1: "in store", 2: "online" };
export const AGE_BUCKETS = ["16-24", "25-34", "35-44", "45-54", "55+", "unknown"];

export const momentKey = ({ day, month, channel }) => `d${day}-m${month}-c${channel}`;

export function parseMoment(key) {
  const [, day, month, channel] = key.match(/d(\d+)-m(\d+)-c(\d+)/).map(Number);
  return { day, month, channel };
}

export function season(month) {
  if (month === 12 || month <= 2) return "winter";
  if (month <= 5) return "spring";
  if (month <= 8) return "summer";
  return "autumn";
}

export function recommendationsFile(shopper) {
  return shopper.kind === "customer"
    ? `moments/${shopper.id}.json`
    : `guests/${shopper.age.replace("+", "plus")}.json`;
}

export const swipeStartKey = (shopper) => (shopper.kind === "customer" ? shopper.id : `guest-${shopper.age}`);

export function formatDate(iso) {
  return new Date(`${iso}T00:00:00`).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}
