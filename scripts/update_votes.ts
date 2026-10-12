// Incrementally add new roll calls (all four chambers) to work/votes/*.json using the same parsers the app uses.
import { readFileSync, writeFileSync } from "node:fs";
import { fetchNewHouseRolls, fetchNewSenateVotes, fetchNewPaRolls, currentCongress } from "../src/lib/live";
import type { RollCall } from "../src/lib/types";
const files = { "US House": "us_house", "US Senate": "us_senate", "PA House": "pa_house", "PA Senate": "pa_senate" } as const;
const now = new Date(); const { congress, session, year } = currentCongress(now);
let failures = 0;
for (const [ch, f] of Object.entries(files) as [RollCall["chamber"], string][]) {
  const path = `work/votes/${f}.json`;
  const cur = JSON.parse(readFileSync(path, "utf8")) as { fetched: string; votes: RollCall[] };
  const pat = ch === "US House" ? `/evs/${year}/` : ch === "US Senate" ? `vote${congress}${session}/` : "";
  const sess = cur.votes.filter((r) => r.src.includes(pat));
  const paSess = ch.startsWith("PA") ? (sess[0]?.src.match(/sessYr=(\d{4})/)?.[1] ?? "") : "";
  const max = Math.max(0, ...sess.filter((r) => !paSess || r.src.includes(`sessYr=${paSess}`)).map((r) => r.roll));
  try {
    const fresh = ch === "US House" ? await fetchNewHouseRolls(year, max, 200) : ch === "US Senate" ? await fetchNewSenateVotes(congress, session, max, 200)
      : await fetchNewPaRolls(ch === "PA House" ? "house" : "senate", max, 200);
    const m = new Map(cur.votes.map((r) => [r.src, r])); for (const r of fresh) m.set(r.src, r);
    const votes = [...m.values()].sort((a, b) => (b.date + String(b.roll).padStart(6, "0")).localeCompare(a.date + String(a.roll).padStart(6, "0")));
    writeFileSync(path, JSON.stringify({ fetched: now.toISOString(), votes }));
    console.log(ch, "new:", fresh.length, "total:", votes.length);
  } catch (e) { failures++; console.log(ch, "UNAVAILABLE:", (e as Error).message); }
}
if (failures === 4) process.exit(1);
