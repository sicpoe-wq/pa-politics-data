// Incremental all-member U.S. House/Senate roll calls -> work/votes_us/*.json (keys "ST:id").
import { readFileSync, writeFileSync } from "node:fs";
import { fetchNewHouseRolls, fetchNewSenateVotes, currentCongress } from "../src/lib/live";
import type { RollCall } from "../src/lib/types";
const now = new Date(); const { congress, session, year } = currentCongress(now);
for (const [f, ch] of [["us_house", "US House"], ["us_senate", "US Senate"]] as const) {
  const path = `work/votes_us/${f}.json`;
  const cur = JSON.parse(readFileSync(path, "utf8")) as { fetched: string; votes: RollCall[] };
  const pat = ch === "US House" ? `/evs/${year}/` : `vote${congress}${session}/`;
  const max = Math.max(0, ...cur.votes.filter((r) => r.src.includes(pat)).map((r) => r.roll));
  try {
    const fresh = ch === "US House" ? await fetchNewHouseRolls(year, max, 200, "*") : await fetchNewSenateVotes(congress, session, max, 200, "*");
    const m = new Map(cur.votes.map((r) => [r.src, r])); for (const r of fresh) m.set(r.src, r);
    const votes = [...m.values()].sort((a, b) => (b.date + String(b.roll).padStart(6, "0")).localeCompare(a.date + String(a.roll).padStart(6, "0")));
    writeFileSync(path, JSON.stringify({ fetched: now.toISOString(), votes }));
    console.log(ch, "all members, new:", fresh.length, "total:", votes.length);
  } catch (e) { console.log(ch, "UNAVAILABLE (keeping saved):", (e as Error).message); }
}
