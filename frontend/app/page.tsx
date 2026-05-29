"use client";

import React from "react";
import type {
  Level, LookupResponse, JurisdictionResponse, RepresentativeResponse, Politician, ErrorKind,
} from "@/lib/types";
import { api, ApiError } from "@/lib/api";
import { BrandMark } from "@/components/ui";
import { Icon } from "@/components/Icon";
import { EntryScreen } from "@/components/EntryScreen";
import { LookupScreen } from "@/components/LookupScreen";
import { RosterScreen } from "@/components/RosterScreen";
import { DetailScreen } from "@/components/DetailScreen";
import { LookupLoading, ErrorScreen } from "@/components/StatusScreens";

type Route = "entry" | "lookup" | "roster" | "detail";

export default function Page() {
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

  const backFromDetail = () => setRoute(cameFromRoster.current ? "roster" : "lookup");
  const backFromRoster = () => setRoute("lookup");
  const editPostal = () => { setLookupErr(null); setRoute("entry"); };
  const home = () => setRoute("entry");

  const showBack = route === "roster" || route === "detail";
  const onBack = route === "detail" ? backFromDetail : backFromRoster;

  return (
    <>
      <header className="app-header">
        <div className="inner">
          <div className="row row-gap-3">
            {showBack ? (
              <button className="btn ghost icon-only" onClick={onBack} aria-label="Back"><Icon name="arrow_left" size={20} /></button>
            ) : null}
            <BrandMark onClick={home} />
          </div>
          {route !== "entry" && postal ? (
            <button className="chip tap outline" onClick={editPostal}>
              <Icon name="map_pin" size={12} /> {api.formatPostalCode(postal)} <Icon name="edit" size={11} />
            </button>
          ) : null}
        </div>
      </header>

      <main key={route}>
        {route === "entry" ? (
          <EntryScreen onSubmit={doLookup} initial={postal ? api.formatPostalCode(postal) : ""} />
        ) : null}

        {route === "lookup" ? (
          loading ? <LookupLoading postal={api.formatPostalCode(postal)} />
          : lookupErr ? <ErrorScreen kind={lookupErr} onRetry={() => doLookup(postal)} onEdit={editPostal} />
          : lookup ? <LookupScreen data={lookup} postal={api.formatPostalCode(postal)} onRep={(r, l) => openRep(r, l, false)} onSeeAll={openRoster} />
          : null
        ) : null}

        {route === "roster" && activeLevel ? (
          <RosterScreen level={activeLevel} data={roster} loading={rosterLoading} onRep={(r, l) => openRep(r, l, true)} />
        ) : null}

        {route === "detail" && activeRep && activeLevel ? (
          <DetailScreen rep={activeRep} level={activeLevel} detail={repDetail} onBack={backFromDetail} onSeeJurisdiction={openRoster} />
        ) : null}
      </main>
    </>
  );
}
