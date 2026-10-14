import { AGE_BUCKETS } from "../data.js";

// Choose whose eyes to shop through: a real customer (a saved sample, or one looked up through
// the live API), or a new visitor by age.
export default function ShopperPicker({ customers, looked: allLooked = [], shopper, onChange }) {
  const looked = allLooked.filter((c) => !customers.some((sample) => sample.id === c.id));
  const value = shopper.kind === "customer" ? `c:${shopper.id}` : `g:${shopper.age}`;

  function handle(event) {
    const [kind, key] = [event.target.value.slice(0, 1), event.target.value.slice(2)];
    const found = looked.find((c) => c.id === key);
    if (kind === "g") onChange({ kind: "guest", age: key });
    else onChange(found ? { kind: "customer", id: key, customerId: found.customerId } : { kind: "customer", id: key });
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
        {looked.length > 0 && (
          <optgroup label="Looked up live">
            {looked.map((c) => (
              <option key={c.id} value={`c:${c.id}`}>
                Customer {c.id} · {c.ageBucket} · {c.purchases.length} buys in 12 weeks
              </option>
            ))}
          </optgroup>
        )}
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
