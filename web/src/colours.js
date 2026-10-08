// H&M colour group names -> a representative colour, for colour cards and the style DNA bar.
const COLOURS = {
  Black: "#1d1c1a",
  White: "#f7f6f2",
  "Off White": "#ece6d8",
  "Light Beige": "#e2d5bd",
  Beige: "#cdb894",
  "Dark Beige": "#a38b66",
  "Greyish Beige": "#b5aa98",
  "Yellowish Brown": "#9a6b35",
  "Light Grey": "#c9c8c4",
  Grey: "#8f8e8a",
  "Dark Grey": "#4d4c49",
  Silver: "#b9bcc0",
  "Light Blue": "#a9c4de",
  Blue: "#3f6fb0",
  "Dark Blue": "#22324f",
  "Light Turquoise": "#a8dcd6",
  Turquoise: "#3aa9a0",
  "Dark Turquoise": "#1f6b66",
  "Light Green": "#bcd9a8",
  Green: "#4f8a45",
  "Dark Green": "#2f4a33",
  "Greenish Khaki": "#7b7a52",
  "Light Yellow": "#f3e7a6",
  Yellow: "#e8c53a",
  "Dark Yellow": "#c39a1c",
  Gold: "#c8a24a",
  "Light Orange": "#f4c39a",
  Orange: "#e5823a",
  "Dark Orange": "#b9561f",
  "Light Red": "#ef9a95",
  Red: "#c23b33",
  "Dark Red": "#7a2329",
  "Light Pink": "#f1cfd3",
  Pink: "#e08aa0",
  "Dark Pink": "#b6476d",
  "Light Purple": "#cbb8dd",
  Purple: "#7a4f9e",
  "Dark Purple": "#45305c",
  Transparent: "#e9eef0",
};

export function colourHex(name) {
  if (COLOURS[name]) return COLOURS[name];
  if (name?.startsWith("Other ")) return COLOURS[name.slice(6)] ?? "#a7a29a";
  return "#a7a29a";
}

// Dark text on light colours, light text on dark ones.
export function inkFor(hex) {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
  return 0.299 * r + 0.587 * g + 0.114 * b > 150 ? "#1b1a17" : "#f7f3ec";
}
