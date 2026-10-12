import { allFloor } from "../src/lib/live";
import { writeFileSync, readFileSync } from "node:fs";
const OUT = process.env.OUT ?? "v1";
const s = await allFloor();
// keep the previous copy of a section whose source is unreachable right now (marked as such)
let prev: any = null; try { prev = JSON.parse(readFileSync(`${OUT}/floor.json`, "utf8")); } catch { /* first run */ }
const merged = s.map((x) => {
  if (x.status !== "unavailable") return x;
  const p = prev?.sections?.find((q: any) => q.key === x.key && q.items?.length);
  return p ? { ...p, message: `${x.message} Showing last saved copy from ${p.fetched.slice(0, 10)}.` } : x;
});
writeFileSync(`${OUT}/floor.json`, JSON.stringify({ fetched: new Date().toISOString(), sections: merged }));
for (const x of merged) console.log(x.key, x.status, x.items.length, x.message ?? "");
