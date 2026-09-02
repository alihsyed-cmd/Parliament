"use client";

import React from "react";
import { useRouter } from "next/navigation";
import type {
  Level, LookupResponse, JurisdictionResponse, RepresentativeResponse, Politician, ErrorKind,
} from "@/lib/types";
import type { Place } from "@/lib/browse-data";
import { api, ApiError } from "@/lib/api";
import {
  CLAIM_AFFORDANCE_VISIBLE, SUBMISSIONS_ENABLED, candidateByUuid, racesFor,
} from "@/lib/candidates";
import { BrandMark } from "@/components/ui";
import { Icon } from "@/components/Icon";
import { EntryScreen } from "@/components/EntryScreen";
import { LookupScreen } from "@/components/LookupScreen";
import { RosterScreen } from "@/components/RosterScreen";
import { DetailScreen } from "@/components/DetailScreen";
import { LookupLoading, ErrorScreen } from "@/components/StatusScreens";
import { BrowsePage, ProvincePage } from "@/components/BrowseScreens";
import { AboutPage, ContactPage, ForCandidatesPage } from "@/components/StaticPages";
import {
  CandidateProfileScreen, RaceChooser, RaceListScreen,
} from "@/components/CandidateScreens";
import { ClaimUnavailable } from "@/components/ClaimScreens";

type Route =
  | "entry" | "lookup" | "roster" | "detail"
  | "browse" | "province-ontario" | "about" | "contact" | "candidates"
  | "race-chooser" | "race-list" | "candidate" | "claim-unavailable";

const NAV_LINKS: { route: Route; label: string; icon: string }[] = [
  { route: "browse", label: "Browse", icon: "search" },
  { route: "about", label: "About", icon: "info" },
  { route: "candidates", label: "For candidates", icon: "star" },
  { route: "contact", label: "Contact", icon: "mail" },
];

const LOOKUP_ROUTES: Route[] = ["lookup", "roster", "detail"];

export default function Page() {
  const router = useRouter();
  const [route, setRoute] = React.useState<Route>("entry");
  const [postal, setPostal] = React.useState("");

  const [lookup, setLookup] = React.useState<LookupResponse | null>(null);
  const [lookupErr, setLookupErr] = React.useState<ErrorKind | null>(null);
  const [loading, setLoading] = React.useState(false);

  const [activeLevel, setActiveLevel] = React.useState<Level | null>(null);
  const [roster, setRoster] = React.useState<JurisdictionResponse | null>(null);
  const [rosterLoading, setRosterLoading] = React.useState(false);

  const [activeRep, setActiveRep] = React.useState<Politician | null>(null);
  const [repDetail, setRepDetail] = React.useState<RepresentativeResponse | null>(null);
  const cameFromRoster = React.useRef(false);

  const [browseFocus, setBrowseFocus] = React.useState<{ section: string; name: string } | null>(null);
  const [raceMuni, setRaceMuni] = React.useState<string | null>(null);
  const [activeRace, setActiveRace] = React.useState<string | null>(null);
  const [activeCandidate, setActiveCandidate] = React.useState<string | null>(null);

  const doLookup = React.useCallback(async (code: string) => {
    const normalized = api.normalizePostalCode(code);
    setPostal(normalized);
    setLookupErr(null);
    setLoading(true);
    setRoute("lookup");
    try {
      setLookup(await api.lookup(normalized));
    } catch (e) {
      setLookupErr(e instanceof ApiError ? e.kind : "server");
    } finally {
      setLoading(false);
    }
  }, []);

  const openRoster = React.useCallback(async (level: Level) => {
    setActiveLevel(level);
    setRoster(null);
    setRoute("roster");
    if (!level.jurisdiction.slug) return;
    setRosterLoading(true);
    try {
      setRoster(await api.jurisdiction(level.jurisdiction.slug));
    } catch {
      setRoster(null);
    } finally {
      setRosterLoading(false);
    }
  }, []);

  const openRep = React.useCallback(async (rep: Politician, level: Level, fromRoster = false) => {
    cameFromRoster.current = fromRoster;
    setActiveRep(rep);
    setActiveLevel(level);
    setRepDetail(null);
    setRoute("detail");
    const jurSlug = level.jurisdiction.slug;
    const repSlug = rep.slug || rep.uuid;
    if (jurSlug && repSlug) {
      try {
        setRepDetail(await api.representative(jurSlug, repSlug));
      } catch {
        setRepDetail(null);
      }
    }
  }, []);

  const editPostal = () => { setLookupErr(null); setRoute("entry"); };
  const home = () => setRoute("entry");

  /**
   * The card promises "your ward", so go straight there when the viewer's ward
   * resolves to a race. The roster is already loaded by the time the card is
   * clickable — it only renders once races are known — so this reads the warm
   * cache rather than waiting again.
   *
   * Falls back to the full chooser when there is no ward to match: an at-large
   * municipality, or a ward with no certified ward race. Going back from the
   * ward race still lands on the chooser, so the mayoral and citywide races
   * stay one tap away.
   */
  const openCandidates = (slug: string, districtId?: string) => {
    setRaceMuni(slug);
    const mine = districtId
      ? racesFor(slug).find(
          (r) => r.jurisdiction_slug === slug && r.district_id === districtId,
        )
      : undefined;
    if (mine) { setActiveRace(mine.key); setRoute("race-list"); return; }
    setRoute("race-chooser");
  };

  const openBrowse = (focus: { section: string; name: string } | null = null) => {
    setBrowseFocus(focus);
    setRoute("browse");
  };

  const onSelectPlace = (place: Place) => {
    if (place.kind === "provincial" && place.covered) { setRoute("province-ontario"); return; }
    openBrowse({ section: place.kind, name: place.name });
  };

  /** Claiming lives on its own route so the emailed-link flow and this one
   *  share a single entry. While the gate is closed nothing here can send. */
  const openClaim = (uuid: string) => {
    if (!SUBMISSIONS_ENABLED) { setActiveCandidate(uuid); setRoute("claim-unavailable"); return; }
    router.push("/claim");
  };

  const BACK: Partial<Record<Route, () => void>> = {
    roster: () => setRoute("lookup"),
    detail: () => setRoute(cameFromRoster.current ? "roster" : "lookup"),
    "province-ontario": () => setRoute("browse"),
    "race-chooser": () => setRoute("lookup"),
    "race-list": () => setRoute("race-chooser"),
    candidate: () => setRoute("race-list"),
    "claim-unavailable": () => setRoute("candidate"),
  };
  const onBack = BACK[route];
  const candidateRow = activeCandidate ? candidateByUuid(activeCandidate) : null;

  return (
    <>
      <header className="app-header">
        <div className="inner">
          <div className="row row-gap-3">
            {onBack ? (
              <button className="btn ghost icon-only" onClick={onBack} aria-label="Back">
                <Icon name="arrow_left" size={20} />
              </button>
            ) : null}
            <BrandMark onClick={home} />
          </div>
          <nav className="nav-links">
            {NAV_LINKS.map((n) => (
              <a key={n.route} href="#" className={route === n.route ? "active" : ""}
                onClick={(e) => { e.preventDefault(); n.route === "browse" ? openBrowse(null) : setRoute(n.route); }}>
                <Icon name={n.icon} size={15} />
                <span className="lbl">{n.label}</span>
              </a>
            ))}
          </nav>
          {LOOKUP_ROUTES.includes(route) && postal ? (
            <button className="chip tap outline" onClick={editPostal}>
              <Icon name="map_pin" size={12} /> {api.formatPostalCode(postal)} <Icon name="edit" size={11} />
            </button>
          ) : null}
        </div>
      </header>

      <main key={route}>
        {route === "entry" ? (
          <EntryScreen onSubmit={doLookup} initial={postal ? api.formatPostalCode(postal) : ""} onSelectPlace={onSelectPlace} />
        ) : null}

        {route === "lookup" ? (
          loading ? <LookupLoading postal={api.formatPostalCode(postal)} />
          : lookupErr ? <ErrorScreen kind={lookupErr} onRetry={() => doLookup(postal)} onEdit={editPostal} />
          : lookup ? (
            <LookupScreen
              data={lookup} postal={api.formatPostalCode(postal)}
              onRep={(r, l) => openRep(r, l, false)} onSeeAll={openRoster}
              onSeeCandidates={openCandidates}
            />
          ) : null
        ) : null}

        {route === "roster" && activeLevel ? (
          <RosterScreen level={activeLevel} data={roster} loading={rosterLoading} onRep={(r, l) => openRep(r, l, true)} />
        ) : null}

        {route === "detail" && activeRep && activeLevel ? (
          <DetailScreen rep={activeRep} level={activeLevel} detail={repDetail}
            onBack={BACK.detail!} onSeeJurisdiction={openRoster} />
        ) : null}

        {route === "browse" ? <BrowsePage focus={browseFocus} onOpenProvince={() => setRoute("province-ontario")} /> : null}
        {route === "province-ontario" ? <ProvincePage /> : null}
        {route === "about" ? <AboutPage /> : null}
        {route === "contact" ? <ContactPage /> : null}
        {route === "candidates" ? (
          <ForCandidatesPage onClaim={CLAIM_AFFORDANCE_VISIBLE ? () => router.push("/claim") : undefined} />
        ) : null}

        {route === "race-chooser" && raceMuni ? (
          <RaceChooser slug={raceMuni} onOpenRace={(key) => { setActiveRace(key); setRoute("race-list"); }} />
        ) : null}
        {route === "race-list" && activeRace ? (
          <RaceListScreen raceKey={activeRace}
            onOpenCandidate={(uuid) => { setActiveCandidate(uuid); setRoute("candidate"); }} />
        ) : null}
        {route === "candidate" && candidateRow ? (
          <CandidateProfileScreen row={candidateRow} onClaim={openClaim} />
        ) : null}
        {route === "claim-unavailable" ? (
          <ClaimUnavailable onBack={() => setRoute(activeCandidate ? "candidate" : "candidates")} />
        ) : null}
      </main>
    </>
  );
}
