"use client";

// app/reminders/unsubscribe/page.tsx — the link in every reminder footer.
//
// One button, no questions, no "are you sure", no survey. Someone who wants out
// gets out in one click, because the alternative to an easy unsubscribe is the
// spam button — and this sending domain also carries candidate claim links that
// have to arrive.
//
// The click is required rather than unsubscribing on page load: mail scanners
// fetch footer links too, and a load-time unsubscribe would quietly drop people
// who never touched it. Gmail's and Yahoo's one-click header is handled
// separately, by a POST straight to the API.

import React from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { unsubscribe } from "@/lib/reminders";
import { BrandMark } from "@/components/ui";
import { Icon } from "@/components/Icon";

type Phase = "ask" | "working" | "done" | "error";

function UnsubscribeInner() {
  const router = useRouter();
  const params = useSearchParams();
  const token = params.get("token") ?? "";

  const [phase, setPhase] = React.useState<Phase>(token ? "ask" : "error");
  const [message, setMessage] = React.useState(
    token ? "" : "That link is missing its code.",
  );

  const go = async () => {
    setPhase("working");
    try {
      await unsubscribe(token);
      setPhase("done");
    } catch (e) {
      setMessage((e as Error).message || "Something went wrong. Please try again.");
      setPhase("error");
    }
  };

  return (
    <div className="container" style={{ paddingTop: 28, paddingBottom: 48, maxWidth: 560 }}>
      {phase === "ask" || phase === "working" ? (
        <div className="stack">
          <h1 className="h-1">Stop election reminders?</h1>
          <p className="t-lead">
            You will no longer get an email before elections where you live.
          </p>
          <button className="act-btn primary" style={{ padding: 13, marginTop: 14 }}
            onClick={go} disabled={phase === "working"}>
            {phase === "working" ? "Stopping…" : "Yes, stop the reminders"}
          </button>
          <button className="btn ghost" style={{ marginTop: 10 }}
            onClick={() => router.push(`/reminders/manage?token=${encodeURIComponent(token)}`)}>
            Keep them, change my postal code instead
          </button>
        </div>
      ) : null}

      {phase === "done" ? (
        <div className="stack">
          <div className="confirm-mark"><Icon name="check" size={22} /></div>
          <h1 className="h-1">Reminders stopped</h1>
          <p className="t-lead">
            You will not receive election reminders. You can start again any time
            from a postal code lookup.
          </p>
          <button className="act-btn primary" style={{ padding: 13, marginTop: 14 }}
            onClick={() => router.push("/")}>
            Go to Parliament
          </button>
        </div>
      ) : null}

      {phase === "error" ? (
        <div className="stack">
          <div className="err-mark"><Icon name="info" size={22} /></div>
          <h1 className="h-1">We could not do that</h1>
          <p className="t-lead">{message}</p>
          <p className="t-sm">
            If you keep receiving reminders you did not ask for, reply to any of
            them and we will remove you by hand.
          </p>
        </div>
      ) : null}
    </div>
  );
}

export default function UnsubscribePage() {
  const router = useRouter();
  return (
    <>
      <header className="app-header">
        <div className="inner"><BrandMark onClick={() => router.push("/")} /></div>
      </header>
      <main>
        <React.Suspense fallback={<div className="container" style={{ paddingTop: 28 }}>
          <p className="t-body">Loading…</p></div>}>
          <UnsubscribeInner />
        </React.Suspense>
      </main>
    </>
  );
}
