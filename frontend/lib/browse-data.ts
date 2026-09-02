// lib/browse-data.ts — Browse tree + place search index.
//
// Place lists ONLY. Every person that used to live here was invented — fake
// mayors, MPPs and MPs pinned to real ridings with real party labels. On a
// live civic site that reads as fact, so it must never ship again.
//
// Populate from GET /search and GET /jurisdictions when they exist. Never
// hand-write officials, and note the `covered` flags below are also unverified.

export interface Place {
  kind: "municipal" | "provincial" | "federal";
  name: string;
  covered: boolean;
  slug?: string;
}

export interface BrowseItem {
  name: string;
  covered: boolean;
  slug?: string;
  mayor?: { full_name: string; initials: string; display_title: string };
  mp?: string;
  party_class?: string;
}

export const PROVINCES: BrowseItem[] = [
  { name: "Alberta", covered: false },
  { name: "British Columbia", covered: false },
  { name: "Manitoba", covered: false },
  { name: "New Brunswick", covered: false },
  { name: "Newfoundland and Labrador", covered: false },
  { name: "Northwest Territories", covered: false },
  { name: "Nova Scotia", covered: false },
  { name: "Nunavut", covered: false },
  { name: "Ontario", covered: true, slug: "ontario" },
  { name: "Prince Edward Island", covered: false },
  { name: "Quebec", covered: false },
  { name: "Saskatchewan", covered: false },
  { name: "Yukon", covered: false },
];

export const ON_MUNICIPALITIES: BrowseItem[] = [
  { name: "Ajax", covered: false },
  { name: "Barrie", covered: false },
  { name: "Brampton", covered: false },
  { name: "Burlington", covered: false },
  { name: "Cambridge", covered: false },
  { name: "Greater Sudbury", covered: false },
  { name: "Guelph", covered: false },
  { name: "Hamilton", covered: false },
  { name: "Kingston", covered: false },
  { name: "Kitchener", covered: false },
  { name: "London", covered: false },
  { name: "Markham", covered: false },
  { name: "Mississauga", covered: true },
  { name: "Oakville", covered: false },
  { name: "Oshawa", covered: false },
  { name: "Ottawa", covered: true },
  { name: "Richmond Hill", covered: false },
  { name: "St. Catharines", covered: false },
  { name: "Thunder Bay", covered: false },
  { name: "Toronto", covered: true },
  { name: "Vaughan", covered: false },
  { name: "Windsor", covered: false },
];

export const ON_MPPS: { uuid: string; full_name: string; district_name: string;
  party_name: string; party_class: string; initials: string }[] = [
  // Emptied: these were invented people. Load from the API, never by hand.
];

export const FEDERAL_RIDINGS: BrowseItem[] = [
  { name: "Beaches–East York", covered: true },
  { name: "Burnaby South", covered: true },
  { name: "Calgary Centre", covered: true },
  { name: "Edmonton Centre", covered: true },
  { name: "Etobicoke North", covered: true },
  { name: "Halifax", covered: true },
  { name: "Hamilton Centre", covered: true },
  { name: "Kitchener Centre", covered: true },
  { name: "London West", covered: true },
  { name: "Markham–Unionville", covered: true },
  { name: "Mississauga–Erin Mills", covered: true },
  { name: "Ottawa Centre", covered: true },
  { name: "Papineau", covered: true },
  { name: "Parkdale–High Park", covered: true },
  { name: "Regina–Wascana", covered: true },
  { name: "Saanich–Gulf Islands", covered: true },
  { name: "Scarborough–Guildwood", covered: true },
  { name: "Spadina–Fort York", covered: true },
  { name: "St. John's East", covered: true },
  { name: "Surrey Centre", covered: true },
  { name: "Thornhill", covered: true },
  { name: "Toronto–Danforth", covered: true },
  { name: "Trois-Rivières", covered: true },
  { name: "Vancouver Granville", covered: true },
  { name: "Victoria", covered: true },
  { name: "Waterloo", covered: true },
  { name: "Whitby", covered: true },
  { name: "Windsor West", covered: true },
  { name: "Winnipeg South", covered: true },
  { name: "York Centre", covered: true },
];

export const PLACE_INDEX: Place[] = [
  ...PROVINCES.map((p) => ({ kind: "provincial" as const, name: p.name, covered: p.covered, slug: p.slug })),
  ...ON_MUNICIPALITIES.map((m) => ({ kind: "municipal" as const, name: m.name, covered: m.covered })),
  ...FEDERAL_RIDINGS.map((r) => ({ kind: "federal" as const, name: r.name, covered: true })),
];
