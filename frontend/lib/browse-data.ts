// lib/browse-data.ts — Browse tree + place search index.
//
// Mock until GET /search and GET /jurisdictions exist. Real jurisdiction names;
// `covered` marks what the database actually holds today.

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
  { name: "Mississauga", covered: true, mayor: { full_name: "Priya Nadarajah", initials: "PN", display_title: "Mayor of Mississauga" } },
  { name: "Oakville", covered: false },
  { name: "Oshawa", covered: false },
  { name: "Ottawa", covered: true, mayor: { full_name: "Étienne Rousseau", initials: "ÉR", display_title: "Mayor of Ottawa" } },
  { name: "Richmond Hill", covered: false },
  { name: "St. Catharines", covered: false },
  { name: "Thunder Bay", covered: false },
  { name: "Toronto", covered: true, mayor: { full_name: "Olivia Khan", initials: "OK", display_title: "Mayor of Toronto" } },
  { name: "Vaughan", covered: false },
  { name: "Windsor", covered: false },
];

export const ON_MPPS = [
  { uuid: "mpp-1", full_name: "Daniel Park", district_name: "Spadina–Fort York", party_name: "New Democratic Party", party_class: "ndp", initials: "DP" },
  { uuid: "mpp-2", full_name: "Farida Aziz", district_name: "Ottawa West–Nepean", party_name: "Progressive Conservative", party_class: "con", initials: "FA" },
  { uuid: "mpp-3", full_name: "Colin Whitfield", district_name: "London North Centre", party_name: "Liberal", party_class: "lib", initials: "CW" },
  { uuid: "mpp-4", full_name: "Meera Chandrasekaran", district_name: "Mississauga–Erin Mills", party_name: "Progressive Conservative", party_class: "con", initials: "MC" },
  { uuid: "mpp-5", full_name: "Jonas Fillion", district_name: "Sudbury", party_name: "New Democratic Party", party_class: "ndp", initials: "JF" },
  { uuid: "mpp-6", full_name: "Rebecca Tsang", district_name: "Hamilton Centre", party_name: "New Democratic Party", party_class: "ndp", initials: "RT" },
  { uuid: "mpp-7", full_name: "Aidan Brophy", district_name: "Kingston and the Islands", party_name: "Liberal", party_class: "lib", initials: "AB" },
  { uuid: "mpp-8", full_name: "Priyanka Sethi", district_name: "Brampton West", party_name: "Progressive Conservative", party_class: "con", initials: "PS" },
];

export const FEDERAL_RIDINGS: BrowseItem[] = [
  { name: "Beaches–East York", covered: true, mp: "Naomi Ferreira", party_class: "lib" },
  { name: "Burnaby South", covered: true, mp: "Tasha Lam", party_class: "ndp" },
  { name: "Calgary Centre", covered: true, mp: "Cole MacDonald", party_class: "con" },
  { name: "Edmonton Centre", covered: true, mp: "Bilal Haidari", party_class: "lib" },
  { name: "Etobicoke North", covered: true, mp: "Adaeze Okafor", party_class: "con" },
  { name: "Halifax", covered: true, mp: "Alex Williams", party_class: "lib" },
  { name: "Hamilton Centre", covered: true, mp: "Ruth Okonkwo", party_class: "ndp" },
  { name: "Kitchener Centre", covered: true, mp: "Simone Vachon", party_class: "green" },
  { name: "London West", covered: true, mp: "Derek Alcott", party_class: "lib" },
  { name: "Markham–Unionville", covered: true, mp: "Grace Yao", party_class: "con" },
  { name: "Mississauga–Erin Mills", covered: true, mp: "Faisal Rahman", party_class: "lib" },
  { name: "Ottawa Centre", covered: true, mp: "Miriam Klassen", party_class: "lib" },
  { name: "Papineau", covered: true, mp: "Léa Bouchard", party_class: "lib" },
  { name: "Parkdale–High Park", covered: true, mp: "Owen Bergeron", party_class: "ndp" },
  { name: "Regina–Wascana", covered: true, mp: "Todd Ferrier", party_class: "con" },
  { name: "Saanich–Gulf Islands", covered: true, mp: "Ines Marchetti", party_class: "green" },
  { name: "Scarborough–Guildwood", covered: true, mp: "Devika Menon", party_class: "lib" },
  { name: "Spadina–Fort York", covered: true, mp: "Sarah Chen", party_class: "ndp" },
  { name: "St. John's East", covered: true, mp: "Patrick Dooley", party_class: "ndp" },
  { name: "Surrey Centre", covered: true, mp: "Harpreet Dhillon", party_class: "lib" },
  { name: "Thornhill", covered: true, mp: "Melissa Groves", party_class: "con" },
  { name: "Toronto–Danforth", covered: true, mp: "Julian Vasquez", party_class: "ndp" },
  { name: "Trois-Rivières", covered: true, mp: "Gabriel Pelletier", party_class: "bloc" },
  { name: "Vancouver Granville", covered: true, mp: "Wei Chang", party_class: "lib" },
  { name: "Victoria", covered: true, mp: "Sian Cormier", party_class: "ndp" },
  { name: "Waterloo", covered: true, mp: "Nadia Petrov", party_class: "lib" },
  { name: "Whitby", covered: true, mp: "Marcus Delgado", party_class: "lib" },
  { name: "Windsor West", covered: true, mp: "Renata Dubois", party_class: "ndp" },
  { name: "Winnipeg South", covered: true, mp: "Hannah Friesen", party_class: "lib" },
  { name: "York Centre", covered: true, mp: "Elias Rosenthal", party_class: "lib" },
];

export const PLACE_INDEX: Place[] = [
  ...PROVINCES.map((p) => ({ kind: "provincial" as const, name: p.name, covered: p.covered, slug: p.slug })),
  ...ON_MUNICIPALITIES.map((m) => ({ kind: "municipal" as const, name: m.name, covered: m.covered })),
  ...FEDERAL_RIDINGS.map((r) => ({ kind: "federal" as const, name: r.name, covered: true })),
];
