// "Why this was picked": short, honest explanations built from the shopper's own data.
// The model's ranking is the real reason; these point at the evidence a shopper can check.
import { CHANNELS, season } from "./data.js";

export function shopperFacts(customer) {
  if (!customer) return null;
  return {
    bought: new Set(customer.purchases.map((p) => p.article_id)),
    topTypes: customer.styleDna.types.slice(0, 3).map(([name]) => name),
    topColours: customer.styleDna.colours.slice(0, 2).map(([name]) => name),
    age: customer.ageBucket,
  };
}

export function reasonsFor(articleId, item, facts, trending, moment, age) {
  const reasons = [];
  if (facts?.bought.has(articleId)) reasons.push("You bought this before");
  if (facts?.topTypes.includes(item.type)) reasons.push(`You often buy ${item.type.toLowerCase()}`);
  if (facts?.topColours.includes(item.colour)) reasons.push(`In your colour: ${item.colour.toLowerCase()}`);
  const group = facts?.age ?? age;
  if (group && group !== "unknown" && trending[group]?.includes(articleId)) {
    reasons.push(`Popular with ${group} shoppers`);
  }
  if (trending.all.slice(0, 50).includes(articleId)) reasons.push("Best-seller last week");
  if (reasons.length === 0 && moment) {
    reasons.push(`Picked for ${season(moment.month)}, ${CHANNELS[moment.channel]}`);
  }
  return reasons.slice(0, 2);
}
