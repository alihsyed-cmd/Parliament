"use client";

import React from "react";
import { Icon } from "./Icon";
import { api } from "@/lib/api";

export function EntryScreen({ onSubmit, initial = "" }: { onSubmit: (postal: string) => void; initial?: string }) {
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
          <div className="eyebrow accent">A parliament for the rest of us</div>
          <h1 className="h-display">
            Meet the people <span className="h-italic serif">who work for you.</span>
          </h1>
          <p className="t-lead">
            Three levels of government. Six elected people, on average. Most Canadians can&apos;t name
            them. We can fix that — together, in under a minute.
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
              Find my reps <Icon name="arrow_right" size={18} />
            </button>
            <p className="t-xs" style={{ textAlign: "center" }}>
              We don&apos;t store your postal code unless you ask us to.
            </p>
          </form>
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
