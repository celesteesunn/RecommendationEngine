import { AGE_BUCKETS } from "../data.js";

// Choose whose eyes to shop through: a real test-week customer, or a new visitor by age.
export default function ShopperPicker({ customers, shopper, onChange }) {
  const value = shopper.kind === "customer" ? `c:${shopper.id}` : `g:${shopper.age}`;

  function handle(event) {
    const [kind, key] = [event.target.value.slice(0, 1), event.target.value.slice(2)];
    onChange(kind === "c" ? { kind: "customer", id: key } : { kind: "guest", age: key });
  }

  return (
    <label className="picker">
      <span className="picker-label">Shopping as</span>
      <select value={value} onChange={handle}>
        <optgroup label="Real shoppers from the test week">
          {customers.map((c) => (
            <option key={c.id} value={`c:${c.id}`}>
              Shopper {c.id} · {c.ageBucket} · {c.warm ? `${c.purchases.length} past buys` : "almost new"}
            </option>
          ))}
        </optgroup>
        <optgroup label="A new visitor (no history)">
          {AGE_BUCKETS.map((age) => (
            <option key={age} value={`g:${age}`}>
              New visitor · {age === "unknown" ? "age not given" : age}
            </option>
          ))}
        </optgroup>
      </select>
    </label>
  );
}
