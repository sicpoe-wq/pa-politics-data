// Gate for publishing: the workflow only commits when every test passes.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import { parseHouseRoll, parseSenateVote, parsePaRoll, parseHouseFloorXml, nextSessionDay, parseCsv } from "../src/lib/live";

const OUT = process.env.OUT ?? "v1";
const J = (p: string) => JSON.parse(readFileSync(`${OUT}/${p}`, "utf8"));
const F = (p: string) => readFileSync(new URL("./fixtures/" + p, import.meta.url), "utf8");
const G = (p: string) => JSON.parse(readFileSync(new URL("./geo/" + p, import.meta.url), "utf8"));
const seatsFile = J("seats.json"); const seats = seatsFile.seats as any[];
const byBody = (b: string) => seats.filter((s) => s.body === b);
const today = new Date().toISOString().slice(0, 10);

test("seat counts are complete", () => {
  assert.equal(seats.length, 284);
  assert.equal(byBody("US Senate").length, 2); assert.equal(byBody("US House").length, 17); assert.equal(byBody("Statewide").length, 5);
  assert.equal(byBody("PA Senate").length, 50); assert.equal(byBody("PA House").length, 203);
  assert.equal(new Set(seats.map((s) => s.id)).size, seats.length);
  for (const [b, n] of [["US House", 17], ["PA Senate", 50], ["PA House", 203]] as const)
    assert.deepEqual(byBody(b).map((s) => s.district).sort((a, b) => a - b), Array.from({ length: n }, (_, i) => i + 1));
});
test("every seat has an incumbent, party, term end and a source", () => {
  for (const s of seats) {
    assert.ok(s.incumbent?.name?.length > 2 && !/[{}\[\]|=]/.test(s.incumbent.name), s.id);
    assert.ok(s.incumbent.party, s.id + " party");
    assert.ok(s.termEnds && /^\d{4}(-\d{2}-\d{2})?$/.test(s.termEnds), s.id + " termEnds " + s.termEnds);
    assert.ok(s.sources.length > 0 && s.sources.every((x: any) => /^https:\/\//.test(x.url)), s.id + " sources");
  }
  const unknown = seats.filter((s) => s.incumbent.party === "Unknown").length;
  assert.ok(unknown <= 3, `too many seats with unknown party (${unknown})`);
});
test("ballot seats have candidate lists with parties", () => {
  const up = seats.filter((s) => s.upIn2026);
  if (today < "2026-11-04") assert.equal(up.length, 17 + 2 + 25 + 203);
  for (const s of up) {
    assert.ok(s.candidates.length >= 1, s.id);
    for (const c of s.candidates) { assert.ok(c.name && !/[{}\[\]|=]/.test(c.name), s.id + " bad name " + c.name); assert.ok(c.party && c.party !== "Unknown", s.id + " party " + c.name); }
  }
});
test("no wholesale incumbent churn vs. last published data (guards against a bad scrape)", () => {
  if (!existsSync(`${OUT}/.prev-seats.json`)) return;
  const prev = new Map((JSON.parse(readFileSync(`${OUT}/.prev-seats.json`, "utf8")).seats as any[]).map((s) => [s.id, s.incumbent.name]));
  const changed = seats.filter((s) => prev.has(s.id) && prev.get(s.id) !== s.incumbent.name);
  const transition = (today >= "2026-11-30" && today <= "2027-01-31") || (today >= "2028-11-30" && today <= "2029-01-31");
  assert.ok(changed.length <= (transition ? 120 : 15), `${changed.length} incumbents changed at once: ${changed.slice(0, 10).map((s) => s.id).join(", ")}`);
});
test("map references resolve to boundary features", () => {
  for (const [layer, file, n] of [["congress", "pa_congress", 17], ["senate", "pa_senate", 50], ["house", "pa_house", 203]] as const) {
    const ds = new Set(G(`${file}.geojson`).features.map((f: any) => f.properties.district));
    assert.equal(ds.size, n, layer);
    for (const s of seats.filter((s) => s.map?.layer === layer)) assert.ok(ds.has(s.map.district), s.id);
  }
});
test("results are internally consistent", () => {
  const r = J("results.json"); const ids = new Set(seats.map((s) => s.id));
  assert.ok(r.elections.length >= 3, "expected past elections");
  for (const e of r.elections) {
    assert.ok(/^\d{4}-\d{2}-\d{2}$/.test(e.date) && ["general", "primary", "special"].includes(e.type), e.key);
    for (const race of e.races) {
      assert.ok(ids.has(race.seat), `${e.key}: unknown seat ${race.seat}`);
      const sum = race.candidates.reduce((a: number, c: any) => a + c.votes, 0);
      assert.equal(sum, race.total, `${e.key} ${race.seat} total`);
      for (const c of race.candidates) assert.ok(Number.isInteger(c.votes) && c.votes >= 0 && c.name, `${e.key} ${race.seat} ${c.name}`);
      if (race.total > 0) assert.ok(Math.abs(race.candidates.reduce((a: number, c: any) => a + c.pct, 0) - 100) < 0.2, `${e.key} ${race.seat} pct`);
    }
  }
  const g24 = r.elections.find((e: any) => e.key.startsWith("2024-G"));
  assert.ok(g24 && g24.races.length >= 245, "2024 general should cover ~249 races");
});
test("votes cover every PA member of Congress", () => {
  const h = J("votes/us_house.json").votes, sn = J("votes/us_senate.json").votes;
  for (const s of byBody("US House")) assert.ok(h.filter((r: any) => r.votes[s.incumbent.bioguide]).length > 50 || s.incumbent.since >= "2026", s.id);
  for (const s of byBody("US Senate")) assert.ok(sn.filter((r: any) => r.votes[s.incumbent.lis]).length > 50, s.id);
  assert.ok(J("votes/pa_house.json").votes.length >= 100 && J("votes/pa_senate.json").votes.length >= 100);
});
test("floor schedule has all four chambers", () => {
  const f = J("floor.json"); assert.deepEqual(f.sections.map((s: any) => s.key).sort(), ["pa-house", "pa-senate", "us-house", "us-senate"]);
});
test("parsers handle real source documents", () => {
  const h = parseHouseRoll(F("house_roll_2026_300.xml"), 2026, 300)!;
  assert.equal(h.date, "2026-09-15"); assert.equal(Object.keys(h.votes).length, 17);
  const s = parseSenateVote(F("senate_vote_119_2_256.xml"), 119, 2, 256)!; assert.deepEqual(s.votes, { S418: "Nay", S433: "Yea" });
  const p = parsePaRoll(F("pa_senate_rc544.html"), "senate", 544, "x")!; assert.equal(Object.keys(p.votes).length, 50);
  const fl = parseHouseFloorXml(F("house_floor_20260914.xml"))!; assert.equal(fl.week, "2026-09-14");
  assert.equal(nextSessionDay(F("pa_house_session_days.html"), new Date(2026, 9, 11)), "2026-10-19");
  assert.deepEqual(parseCsv('a,b\n"x, y",2\n'), [{ a: "x, y", b: "2" }]);
});
test("candidate events are well-formed and attributable", () => {
  const ev = J("events.json"); const now = Date.now();
  assert.ok(Array.isArray(ev.status) && ev.status.length >= 2);
  const keys = new Set(seats.flatMap((s) => s.candidates.map((c: any) => `${s.id}|${c.name}`)));
  for (const [k, v] of Object.entries(ev.byCandidate) as [string, any][]) {
    assert.ok(keys.has(k), "event for unknown candidate " + k);
    for (const e of v.events) {
      assert.ok(e.id && e.title && e.kind && ["Mobilize", "Wikipedia"].includes(e.source), k + " " + e.id);
      assert.ok(/^https:\/\//.test(e.url), k + " url " + e.url);
      const t = Date.parse(e.start); assert.ok(!isNaN(t), k + " start " + e.start);
      assert.ok(t > now - (ev.pastDays + 2) * 864e5, k + " too old " + e.start);
      assert.equal(e.timeKnown, /T\d\d:/.test(e.start));
    }
    for (const l of v.links) assert.ok(/^https:\/\//.test(l.url) && l.label, k + " link");
  }
});
