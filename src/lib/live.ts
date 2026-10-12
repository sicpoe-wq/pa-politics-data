// Live fetchers for free, no-key public sources. Pure regex parsing so the same code
// runs in the Android WebView (via CapacitorHttp, no CORS limits) and in Node at build time.
import type { RollCall, FloorSection, FloorItem } from "./types";

const UA_HEADERS: Record<string, string> = {};
export async function fetchText(url: string, timeoutMs = 25000): Promise<{ status: number; text: string }> {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), timeoutMs);
  try {
    const r = await fetch(url, { signal: ctl.signal, headers: UA_HEADERS });
    return { status: r.status, text: await r.text() };
  } finally {
    clearTimeout(t);
  }
}

const decode = (s: string) =>
  s.replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, "$1").replace(/&nbsp;/g, " ").replace(/&amp;/g, "&").replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&#39;|&#x27;/g, "'").replace(/&#x26;/g, "&")
    .replace(/&#(\d+);/g, (_, n) => String.fromCharCode(+n));
const strip = (s: string) => decode(s.replace(/<[^>]+>/g, " ")).replace(/\s+/g, " ").trim();
const tag = (xml: string, name: string) => {
  const m = new RegExp(`<${name}(?:\\s[^>]*)?>([\\s\\S]*?)</${name}>`).exec(xml);
  return m ? decode(m[1]).replace(/\s+/g, " ").trim() : "";
};
const MONTHS: Record<string, string> = { jan: "01", feb: "02", mar: "03", apr: "04", may: "05", jun: "06", jul: "07", aug: "08", sep: "09", oct: "10", nov: "11", dec: "12" };
const pad = (n: number | string) => String(n).padStart(2, "0");

// ---------------- US House (Clerk roll-call XML) ----------------
export function parseHouseRoll(xml: string, year: number, n: number): RollCall | null {
  if (!xml.includes("<rollcall-vote")) return null;
  const d = /(\d{1,2})-([A-Za-z]{3})-(\d{4})/.exec(tag(xml, "action-date"));
  const votes: Record<string, string> = {};
  const re = /<recorded-vote>\s*<legislator([^>]*)>[\s\S]*?<\/legislator>\s*<vote>([^<]*)<\/vote>/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(xml))) {
    if (/state="PA"/.test(m[1])) { const id = /name-id="([^"]+)"/.exec(m[1]); if (id) votes[id[1]] = m[2].trim(); }
  }
  const tot = /<totals-by-vote>([\s\S]*?)<\/totals-by-vote>/.exec(xml)?.[1] ?? "";
  return {
    chamber: "US House", roll: n, date: d ? `${d[3]}-${MONTHS[d[2].toLowerCase()]}-${pad(d[1])}` : "",
    bill: tag(xml, "legis-num"), question: tag(xml, "vote-question"), title: tag(xml, "vote-desc"), result: tag(xml, "vote-result"),
    tally: tot ? `${tag(tot, "yea-total")}-${tag(tot, "nay-total")}` : "",
    url: `https://clerk.house.gov/Votes/${year}${n}`, src: `https://clerk.house.gov/evs/${year}/roll${String(n).padStart(3, "0")}.xml`, votes,
  };
}
export async function fetchNewHouseRolls(year: number, after: number, max = 60): Promise<RollCall[]> {
  const out: RollCall[] = [];
  for (let n = after + 1; n <= after + max; n++) {
    const r = await fetchText(`https://clerk.house.gov/evs/${year}/roll${String(n).padStart(3, "0")}.xml`);
    const rc = r.status === 200 ? parseHouseRoll(r.text, year, n) : null;
    if (!rc) break;
    out.push(rc);
  }
  return out;
}

// ---------------- US Senate (senate.gov LIS XML) ----------------
export function parseSenateVote(xml: string, cong: number, sess: number, n: number): RollCall | null {
  if (!xml.includes("<roll_call_vote")) return null;
  const dm = /([A-Za-z]+) (\d{1,2}), (\d{4})/.exec(tag(xml, "vote_date"));
  const votes: Record<string, string> = {};
  const re = /<member>([\s\S]*?)<\/member>/g; let m: RegExpExecArray | null;
  while ((m = re.exec(xml))) if (tag(m[1], "state") === "PA") votes[tag(m[1], "lis_member_id")] = tag(m[1], "vote_cast");
  const doc = /<document>([\s\S]*?)<\/document>/.exec(xml)?.[1] ?? "";
  const nn = String(n).padStart(5, "0");
  const base = `https://www.senate.gov/legislative/LIS/roll_call_votes/vote${cong}${sess}/vote_${cong}_${sess}_${nn}`;
  return {
    chamber: "US Senate", roll: n, date: dm ? `${dm[3]}-${MONTHS[dm[1].slice(0, 3).toLowerCase()]}-${pad(dm[2])}` : "",
    bill: tag(doc, "document_name") || `${tag(doc, "document_type")} ${tag(doc, "document_number")}`.trim(),
    question: tag(xml, "question"), title: tag(xml, "vote_title") || tag(xml, "vote_document_text"),
    result: tag(xml, "vote_result_text") || tag(xml, "vote_result"),
    tally: `${tag(xml.split("<count>")[1] ?? "", "yeas")}-${tag(xml.split("<count>")[1] ?? "", "nays")}`,
    url: base + ".htm", src: base + ".xml", votes,
  };
}
export async function fetchNewSenateVotes(cong: number, sess: number, after: number, max = 60): Promise<RollCall[]> {
  const menu = await fetchText(`https://www.senate.gov/legislative/LIS/roll_call_lists/vote_menu_${cong}_${sess}.xml`);
  if (menu.status !== 200) throw new Error(`senate.gov vote menu HTTP ${menu.status}`);
  const nums = [...menu.text.matchAll(/<vote_number>(\d+)<\/vote_number>/g)].map((m) => +m[1]);
  const latest = Math.max(0, ...nums);
  const out: RollCall[] = [];
  for (let n = latest; n > after && out.length < max; n--) {
    const nn = String(n).padStart(5, "0");
    const r = await fetchText(`https://www.senate.gov/legislative/LIS/roll_call_votes/vote${cong}${sess}/vote_${cong}_${sess}_${nn}.xml`);
    const rc = r.status === 200 ? parseSenateVote(r.text, cong, sess, n) : null;
    if (rc) out.push(rc);
  }
  return out;
}

// ---------------- PA General Assembly (palegis.us) ----------------
export function parsePaRoll(html: string, body: "house" | "senate", n: number, url: string): RollCall | null {
  const plain = strip(html.replace(/<script[\s\S]*?<\/script>/g, ""));
  let date = "", bill = "", action = "", title = "", y = "", nn = "";
  let m = /Details for RCS No\. \d+ Vote Date (.*?) Bill (.*?) Action (.*?) Short Title (.*?) Prime Sponsor (.*?) Vote Summary Yea (\d+) Nay (\d+)/.exec(plain);
  if (m) [, date, bill, action, title, , y, nn] = m;
  else if ((m = /Details for RCS No\. \d+ Vote Date (.*?) (?:Action|Motion|Description) (.*?) Vote Summary Yea (\d+) Nay (\d+)/.exec(plain))) [, date, action, y, nn] = m;
  else if ((m = /Details for RCS No\. \d+ Vote Date (.*?) Vote Summary Yea (\d+) Nay (\d+)/.exec(plain))) [, date, y, nn] = m;
  else return null;
  const dm = /([A-Z][a-z]+) (\d{1,2}), (\d{4})/.exec(date);
  const votes: Record<string, string> = {};
  for (const blk of html.split('class="rc-member d-flex').slice(1)) {
    const dist = /(?:House|Senate) District&nbsp;(\d+)/.exec(blk);
    const v = /badge text-bg-[a-z-]+" title="([^"]+)"/.exec(blk);
    const nm = /<a href='\/(?:house|senate)\/members\/bio\/[^']*'[^>]*>(?:Rep\.|Sen\.)?\s*([^<]+)<\/a>/.exec(blk);
    if (dist && v) votes[dist[1]] = `${v[1]}|${nm ? decode(nm[1]).trim() : ""}`;
  }
  return {
    chamber: body === "house" ? "PA House" : "PA Senate", roll: n,
    date: dm ? `${dm[3]}-${MONTHS[dm[1].slice(0, 3).toLowerCase()]}-${pad(dm[2])}` : "",
    bill: bill.replace("House Bill", "HB").replace("Senate Bill", "SB").replace("House Resolution", "HR").replace("Senate Resolution", "SR"),
    question: action.replace(/ - opens in a new tab/g, ""), title, result: "", tally: `${y}-${nn}`, url, src: url, votes,
  };
}
export async function fetchNewPaRolls(body: "house" | "senate", after: number, max = 40): Promise<RollCall[]> {
  const rss = await fetchText(`https://www.palegis.us/${body}/rss/session/votes`);
  if (rss.status !== 200) throw new Error(`palegis.us ${body} roll-call RSS HTTP ${rss.status}`);
  const nums = [...rss.text.matchAll(/rcNum=(\d+)/g)].map((m) => +m[1]);
  const sess = /sessYr=(\d{4})/.exec(rss.text)?.[1] ?? "2025";
  const latest = Math.max(0, ...nums);
  const out: RollCall[] = [];
  for (let n = latest; n > after && out.length < max; n--) {
    const url = `https://www.palegis.us/${body}/roll-calls/summary?sessYr=${sess}&sessInd=0&rcNum=${n}`;
    const r = await fetchText(url);
    const rc = r.status === 200 ? parsePaRoll(r.text, body, n, url) : null;
    if (rc) out.push(rc);
  }
  return out;
}

// ---------------- Upcoming floor action ----------------
const nowIso = () => new Date().toISOString();
function mondayOf(d: Date) { const x = new Date(d); const day = (x.getDay() + 6) % 7; x.setDate(x.getDate() - day); return x; }
const ymd = (d: Date) => `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}`;

export function parseHouseFloorXml(xml: string): { week: string; items: FloorItem[] } | null {
  if (!xml.includes("<floorschedule")) return null;
  const week = /week-date="([^"]+)"/.exec(xml)?.[1] ?? "";
  const items: FloorItem[] = [];
  for (const cat of xml.matchAll(/<category type="([^"]*)"[\s\S]*?<\/category>/g)) {
    for (const it of cat[0].matchAll(/<floor-item [^>]*remove-date="([^"]*)"[^>]*>([\s\S]*?)<\/floor-item>/g)) {
      if (it[1]) continue; // removed from schedule
      const pdf = /doc-url="([^"]+)"/.exec(it[2])?.[1];
      items.push({ bill: tag(it[2], "legis-num"), title: tag(it[2], "floor-text"), detail: decode(cat[1]), link: pdf?.replace(/^http:/, "https:") });
    }
  }
  return { week, items };
}
export async function usHouseFloor(today = new Date()): Promise<FloorSection> {
  const base: FloorSection = { key: "us-house", chamber: "US House", heading: "U.S. House floor schedule", status: "unavailable", items: [],
    sourceName: "House Majority Leader / docs.house.gov weekly floor schedule (XML)", sourceUrl: "https://docs.house.gov/floor/", fetched: nowIso() };
  try {
    const wk = ymd(mondayOf(today));
    let r = await fetchText(`https://docs.house.gov/floor/Download.aspx?file=/billsthisweek/${wk}/${wk}.xml`);
    let p = r.status === 200 ? parseHouseFloorXml(r.text) : null;
    let stale = false;
    if (!p) {
      const idx = await fetchText("https://docs.house.gov/floor/");
      const f = /Download\.aspx\?file=(\/billsthisweek\/\d+\/\d+\.xml)/.exec(idx.text)?.[1];
      if (f) { r = await fetchText(`https://docs.house.gov/floor/Download.aspx?file=${f}`); p = parseHouseFloorXml(r.text); stale = true; }
    }
    if (!p) return { ...base, message: "Floor schedule could not be read." };
    const weekEnd = new Date(p.week + "T12:00:00"); weekEnd.setDate(weekEnd.getDate() + 7);
    stale = stale || weekEnd < today;
    return { ...base, status: p.items.length ? "ok" : "empty", date: p.week,
      heading: `U.S. House – week of ${p.week}`,
      message: stale ? `No schedule is posted for the current week (the House may be in recess). Showing the most recent posted week (${p.week}).` : undefined,
      items: p.items, sourceUrl: `https://docs.house.gov/floor/Default.aspx?date=${p.week}` };
  } catch (e) { return { ...base, message: `Unavailable: ${(e as Error).message}` }; }
}
export async function usSenateFloor(): Promise<FloorSection> {
  const base: FloorSection = { key: "us-senate", chamber: "US Senate", heading: "U.S. Senate floor schedule", status: "unavailable", items: [],
    sourceName: "senate.gov floor schedule", sourceUrl: "https://www.senate.gov/legislative/floor_activity_pail.htm", fetched: nowIso() };
  try {
    const r = await fetchText("https://www.senate.gov/legislative/schedule/floor_schedule.htm");
    if (r.status !== 200) return { ...base, message: `Unavailable (HTTP ${r.status})` };
    const art = /<article id="proceedings_schedule"[\s\S]*?<\/article>/.exec(r.text)?.[0] ?? "";
    const date = strip(/<h3>([\s\S]*?)<\/h3>/.exec(art)?.[1] ?? "");
    const sched = strip(/<span class="floor-schedule">([\s\S]*?)<\/span>/.exec(art)?.[1] ?? "");
    if (!date && !sched) return { ...base, message: "Schedule text not found on senate.gov." };
    return { ...base, status: "ok", date, heading: `U.S. Senate – next meeting ${date}`,
      items: [{ bill: date, title: sched || "(no details posted)", detail: "senate.gov does not publish a bill-by-bill weekly list; see the Senate Calendar of Business / Executive Calendar for pending measures.", link: "https://www.senate.gov/legislative/LIS/executive_calendar/xcalv.pdf" }] };
  } catch (e) { return { ...base, message: `Unavailable: ${(e as Error).message}` }; }
}
export function nextSessionDay(html: string, today = new Date()): string | null {
  const text = strip(html.replace(/<script[\s\S]*?<\/script>/g, ""));
  const yrs = [...text.matchAll(/(\d{4}) Session Days (.*?)(?=\d{4} Session Days|Looking for prior|$)/g)];
  const months = ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"];
  const t0 = `${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(today.getDate())}`;
  const dates: string[] = [];
  for (const [, yr, body] of yrs) {
    let mon = -1;
    for (const tok of body.split(" ")) {
      const mi = months.indexOf(tok);
      if (mi >= 0) { mon = mi; continue; }
      if (/^\d{1,2}$/.test(tok) && mon >= 0) dates.push(`${yr}-${pad(mon + 1)}-${pad(tok)}`);
    }
  }
  return dates.filter((d) => d >= t0).sort()[0] ?? null;
}
export async function paFloor(body: "house" | "senate", today = new Date()): Promise<FloorSection> {
  const chamber = body === "house" ? "PA House" : "PA Senate";
  const base: FloorSection = { key: "pa-" + body, chamber, heading: `${chamber} session calendar`, status: "unavailable", items: [],
    sourceName: `palegis.us ${chamber} session calendar (RSS)`, sourceUrl: `https://www.palegis.us/${body}/session/calendars`, fetched: nowIso() };
  try {
    const [cal, days] = await Promise.all([fetchText(`https://www.palegis.us/${body}/rss/session/calendar`), fetchText(`https://www.palegis.us/${body}/session?days`)]);
    if (cal.status !== 200) return { ...base, message: `Unavailable (HTTP ${cal.status})` };
    const next = days.status === 200 ? nextSessionDay(days.text, today) : null;
    const items: FloorItem[] = [];
    for (const it of cal.text.matchAll(/<item>([\s\S]*?)<\/item>/g)) {
      const t = tag(it[1], "title");
      const bill = t.replace(/House Bill/, "HB").replace(/Senate Bill/, "SB").replace(/House Resolution/, "HR").replace(/Senate Resolution/, "SR").replace(/Printer's Number/, "PN");
      const analysis = tag(it[1], "parss:Analysis");
      const desc = tag(it[1], "description");
      const cat = tag(it[1], "category").replace(/\|/g, " · ");
      const spons = tag(it[1], "parss:Sponsors");
      items.push({ bill, title: analysis || desc, detail: [cat, spons].filter(Boolean).join(" — "), link: decode(tag(it[1], "link")) });
    }
    return { ...base, status: items.length ? "ok" : "empty", date: next ?? undefined,
      heading: next ? `${chamber} – next session day ${next}` : `${chamber} session calendar`,
      message: "Bills on the calendar for the next session day (palegis.us lists what may be considered; not every bill gets a vote).", items };
  } catch (e) { return { ...base, message: `Unavailable: ${(e as Error).message}` }; }
}
export async function allFloor(): Promise<FloorSection[]> {
  return Promise.all([usHouseFloor(), usSenateFloor(), paFloor("house"), paFloor("senate")]);
}

// ---------------- Incumbent refresh ----------------
export function parseCsv(text: string): Record<string, string>[] {
  const rows: string[][] = []; let row: string[] = []; let f = ""; let q = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) { if (c === '"') { if (text[i + 1] === '"') { f += '"'; i++; } else q = false; } else f += c; }
    else if (c === '"') q = true;
    else if (c === ",") { row.push(f); f = ""; }
    else if (c === "\n") { row.push(f); rows.push(row); row = []; f = ""; }
    else if (c !== "\r") f += c;
  }
  if (f || row.length) { row.push(f); rows.push(row); }
  const [h, ...rest] = rows;
  return rest.filter((r) => r.length === h.length).map((r) => Object.fromEntries(h.map((k, i) => [k, r[i]])));
}

/** U.S. Congress number/session and roll-call year for a date (sessions start Jan 3). */
export function currentCongress(d = new Date()) {
  const year = d.getFullYear();
  return { year, congress: 119 + Math.floor((year - 2025) / 2), session: year % 2 === 1 ? 1 : 2 };
}
