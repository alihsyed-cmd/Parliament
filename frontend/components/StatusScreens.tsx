"use client";

import React from "react";
import { Skeleton, Spinner } from "./ui";
import { Icon } from "./Icon";
import type { ErrorKind } from "@/lib/types";

export function LookupLoading({ postal }: { postal: string }) {
  return (
    <div className="container fade-in">
      <div className="stack stack-3" style={{ marginBottom: 22 }}>
        <div className="eyebrow accent">Looking up {postal}</div>
        <Skeleton w="70%" h={36} r={8} />
        <Skeleton w="90%" h={16} />
      </div>
      <div className="levels-grid">
        {[0, 1, 2].map((i) => (
          <div className="card" key={i} style={{ padding: 18 }}>
            <div className="row row-gap-3">
              <Skeleton w={44} h={44} r={12} />
              <div className="stack stack-2 fill">
                <Skeleton w="55%" h={13} />
                <Skeleton w="75%" h={20} />
              </div>
            </div>
          </div>
        ))}
      </div>
      <div className="row row-gap-2" style={{ justifyContent: "center", marginTop: 24, color: "var(--ink-3)" }}>
        <Spinner size={14} /> <span className="t-xs">Finding your districts…</span>
      </div>
    </div>
  );
}

const ERROR_COPY: Record<ErrorKind, { eyebrow: string; title: string; body: string }> = {
  network:   { eyebrow: "Offline", title: "Can't reach the server right now.", body: "Check your connection and try again. If this is the first request in a while, the server may be waking up — give it a moment." },
  invalid:   { eyebrow: "Hmm", title: "That doesn't look like a postal code.", body: "Postal codes look like A1A 1A1." },
  not_found: { eyebrow: "No match", title: "We couldn't find that postal code.", body: "Double-check the spelling, or try a nearby one." },
  server:    { eyebrow: "Error", title: "Something went wrong on our end.", body: "We've been notified. Please try again in a moment." },
};

export function ErrorScreen({
  kind, onRetry, onEdit,
}: { kind: ErrorKind; onRetry?: () => void; onEdit: () => void }) {
  const c = ERROR_COPY[kind] ?? ERROR_COPY.server;
  return (
    <div className="container fade-in">
      <div className="stack stack-4" style={{ maxWidth: 460 }}>
        <div className="eyebrow accent">{c.eyebrow}</div>
        <h1 className="h-1">{c.title}</h1>
        <p className="t-lead">{c.body}</p>
        <div className="stack stack-3" style={{ marginTop: 8 }}>
          <button className="btn primary lg block" onClick={onEdit}>Try another postal code</button>
          {kind === "network" && onRetry ? (
            <button className="btn outline block" onClick={onRetry}>Retry</button>
          ) : null}
        </div>
      </div>
    </div>
  );
}
