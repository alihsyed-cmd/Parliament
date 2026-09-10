"use client";

import React from "react";
import { Icon } from "./Icon";
import { api } from "@/lib/api";
import type { Place } from "@/lib/browse-data";
import { SearchPlaces } from "./StaticPages";

export function EntryScreen({
  onSubmit, initial = "", onSelectPlace,
}: {
  onSubmit: (postal: string) => void;
  initial?: string;
  onSelectPlace?: (p: Place) => void;
}) {
  const [value, setValue] = React.useState(initial);
  const valid = api.isValidPostalCode(value);

  const onChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    let v = e.target.value.toUpperCase().replace(/[^A-Z0-9 ]/g, "");
    const raw = v.replace(/\s/g, "");
    v = raw.length > 3 ? `${raw.slice(0, 3)} ${raw.slice(3, 6)}` : raw;
    setValue(v);
  };

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (valid) onSubmit(api.normalizePostalCode(value));
  };

  return (
    <div className="container fade-in">
      <div className="entry-grid">
        <div className="stack stack-4">
          <div className="eyebrow accent">Civic information for Canadians</div>
          <h1 className="h-display">
            Know the people <span className="h-italic serif">who represent you.</span>
          </h1>
          <p className="t-lead">
            Every Canadian has representatives at three levels of government. Enter your postal code
            to see all of them, with a direct way to reach each one. Where an election is coming,
            you&apos;ll also see everyone running.
          </p>

          <form onSubmit={submit} className="stack stack-3" style={{ marginTop: 8, maxWidth: 460 }}>
            <div>
              <div className="field-label">Your postal code</div>
              <div className="field" style={{ borderColor: valid ? "var(--ink)" : "var(--line)" }}>
                <Icon name="map_pin" size={18} />
                <input
                  value={value} onChange={onChange}
                  placeholder="A1A 1A1" maxLength={7}
                  autoComplete="postal-code" inputMode="text"
                  aria-label="Postal code"
                />
              </div>
            </div>
            <button type="submit" className="btn primary block lg" disabled={!valid} style={{ opacity: valid ? 1 : 0.55 }}>
              Find my representatives <Icon name="arrow_right" size={18} />
            </button>
            <p className="t-xs" style={{ textAlign: "center" }}>
              Your postal code isn&apos;t stored unless you ask us to save it.
            </p>
          </form>

          {onSelectPlace ? (
            <div style={{ marginTop: 18, maxWidth: 460 }}>
              <div className="t-xs" style={{ marginBottom: 8 }}>Looking somewhere else?</div>
              <SearchPlaces onSelect={onSelectPlace} />
            </div>
          ) : null}
        </div>

        <div>
          <div className="hero-illu">
            <div className="pillar muni" />
            <div className="pillar prov" />
            <div className="pillar fed" />
          </div>
          <div className="labels"><span>Municipal</span><span>Provincial</span><span>Federal</span></div>
        </div>
      </div>
    </div>
  );
}
