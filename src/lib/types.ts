export type Source = { name: string; url: string; retrieved: string };
export type Candidate = { name: string; party: string; incumbent: boolean; note?: string };
export type Incumbent = {
  name: string; party: string; photo?: string | null; since?: string | null; url?: string | null;
  bioguide?: string; lis?: string; email?: string | null; phone?: string | null; office?: string; openstates?: string;
};
export type Seat = {
  id: string; level: string; body: string; title: string; district: number | null; counties?: string | null;
  incumbent: Incumbent; termEnds: string | null; termEndsNote?: string; nextElection: string | null; upIn2026: boolean;
  candidates: Candidate[]; candidatesStatus: "verified" | "unknown" | "not-yet" | "not-applicable";
  notes: string[]; sources: Source[]; map: { layer: Layer; district: number } | null;
};
export type Layer = "congress" | "senate" | "house";
export type SeatsFile = { generated: string; nextGeneralElection: string; seats: Seat[] };
export type RollCall = {
  chamber: "US House" | "US Senate" | "PA House" | "PA Senate";
  roll: number; date: string; bill: string; question: string; title: string; result: string; tally: string;
  url: string; src: string; votes: Record<string, string>;
};
export type VoteFile = { fetched: string; votes: RollCall[] };
export type FloorItem = { bill: string; title: string; detail?: string; link?: string };
export type FloorSection = {
  key: string; chamber: string; heading: string; date?: string; status: "ok" | "unavailable" | "empty";
  message?: string; items: FloorItem[]; sourceName: string; sourceUrl: string; fetched: string;
};
