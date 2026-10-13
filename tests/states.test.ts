// 50-state gate (v2). Publishing happens only if every test passes.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
const J = (p: string) => JSON.parse(readFileSync(`v2/${p}`, "utf8"));
const index = J("index.json").states as any[];
const today = new Date().toISOString().slice(0, 10);
const APPORT: Record<string, number> = { AL: 7, AK: 1, AZ: 9, AR: 4, CA: 52, CO: 8, CT: 5, DE: 1, FL: 28, GA: 14, HI: 2, ID: 2, IL: 17, IN: 9, IA: 4, KS: 4, KY: 6, LA: 6, ME: 2, MD: 8, MA: 9, MI: 13, MN: 8, MS: 4, MO: 8, MT: 2, NE: 3, NV: 4, NH: 2, NJ: 12, NM: 3, NY: 26, NC: 14, ND: 1, OH: 15, OK: 5, OR: 6, PA: 17, RI: 2, SC: 7, SD: 1, TN: 9, TX: 38, UT: 4, VT: 1, VA: 11, WA: 10, WV: 2, WI: 8, WY: 1 };
const BAD = /[{}\[\]|=]/;
test("index lists all 50 states", () => {
  assert.equal(index.length, 50); assert.deepEqual(index.map((s) => s.code).sort(), Object.keys(APPORT).sort());
});
for (const st of index) {
  test(`${st.code}: seats`, () => {
    const seats = J(`states/${st.code}/seats.json`).seats as any[];
    assert.equal(new Set(seats.map((s) => s.id)).size, seats.length, "duplicate ids");
    assert.equal(seats.filter((s) => s.body === "US Senate").length, 2);
    assert.equal(seats.filter((s) => s.body === "US House").length, APPORT[st.code]);
    assert.ok(seats.some((s) => s.body === "Statewide" && /Governor/.test(s.title)), "governor");
    for (const s of seats) {
      assert.ok(s.incumbent?.name && !BAD.test(s.incumbent.name), `${s.id} incumbent`);
      assert.ok(s.sources.length && s.sources.every((x: any) => /^https:\/\//.test(x.url)), `${s.id} sources`);
      for (const c of s.candidates) assert.ok(c.name && !BAD.test(c.name) && c.party, `${s.id} candidate ${c.name}`);
      if (s.termEnds) assert.match(s.termEnds, /^\d{4}(-\d{2}-\d{2})?$/);
    }
    const vac = seats.filter((s) => s.incumbent.name === "Vacant").length; assert.ok(vac <= 3, `${vac} vacancies`);
    // federal + governor races on the 2026 ballot should have candidate lists (until results replace them)
    if (today < "2026-11-04") {
      const up = seats.filter((s) => ["US House", "US Senate", "Statewide"].includes(s.body) && s.upIn2026);
      const miss = up.filter((s) => !s.candidates.length).map((s) => s.id);
      assert.ok(miss.length <= Math.max(1, up.length * 0.1), "missing candidates: " + miss.join(","));
    }
    const leg = seats.filter((s) => s.body === "State Senate" || s.body === "State House").length;
    assert.ok(leg >= 40, `only ${leg} state legislators (Open States)`);
  });
  test(`${st.code}: maps resolve`, () => {
    const seats = J(`states/${st.code}/seats.json`).seats as any[];
    for (const layer of st.layers) {
      const ds = new Set(J(`states/${st.code}/geo/${layer}.geojson`).features.map((f: any) => f.properties.district));
      const refs = seats.filter((s) => s.map?.layer === layer);
      for (const s of refs) assert.ok(ds.has(s.map.district), `${s.id} -> ${s.map.district}`);
      if (layer === "congress") assert.equal(ds.size, APPORT[st.code]);
    }
    assert.ok(st.layers.includes("congress") && st.layers.includes("senate"));
  });
  test(`${st.code}: congressional votes and events`, () => {
    const seats = J(`states/${st.code}/seats.json`).seats as any[];
    const h = J(`states/${st.code}/votes/us_house.json`).votes, s = J(`states/${st.code}/votes/us_senate.json`).votes;
    const withVotes = seats.filter((x) => x.body === "US House" && x.incumbent.bioguide && Object.values(h).some((v: any) => v[x.incumbent.bioguide])).length;
    assert.ok(withVotes >= seats.filter((x) => x.body === "US House" && x.incumbent.bioguide).length - 2, "house members without votes");
    assert.ok(Object.keys(s).length > 100, "senate votes");
    if (existsSync(`v2/states/${st.code}/events.json`)) {
      const ev = J(`states/${st.code}/events.json`); const keys = new Set(seats.flatMap((x) => x.candidates.map((c: any) => `${x.id}|${c.name}`)));
      for (const [k, v] of Object.entries(ev.byCandidate) as [string, any][]) {
        assert.ok(keys.has(k), "unknown candidate " + k);
        for (const e of v.events) assert.ok(/^https:\/\//.test(e.url) && !isNaN(Date.parse(e.start)), k);
      }
    }
  });
}
test("national roll-call metadata", () => {
  for (const f of ["us_house", "us_senate"]) { const n = J(`national/${f}.json`); assert.ok(n.rolls.length > 300); for (const r of n.rolls.slice(0, 20)) assert.ok(r.src && r.date); }
});
