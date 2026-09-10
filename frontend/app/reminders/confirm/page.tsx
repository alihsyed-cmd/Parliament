"use client";

// app/reminders/confirm/page.tsx — the target of the confirmation link.
//
// The link is a GET, but confirming is a POST this page makes on the visitor's
// behalf. That indirection is the point of double opt-in: corporate mail
// scanners and link-preview bots fetch every URL in an inbound message, and a
// GET that confirmed directly would let a scanner establish consent the human
// never gave. A bot does not run this page's JavaScript.

import React from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { confirm, type UpcomingElection } from "@/lib/reminders";
import { UpcomingList } from "@/components/ReminderToggle";
import { BrandMark } from "@/components/ui";
import { Icon } from "@/components/Icon";

type Phase = "working" | "done" | "error";

function ConfirmInner() {
  const router = useRouter();
  const params = useSearchParams();
  const token = params.get("token") ?? "";

  const [phase, setPhase] = React.useState<Phase>("working");
  const [message, setMessage] = React.useState("");
  const [postal, setPostal] = React.useState("");
  const [upcoming, setUpcoming] = React.useState<UpcomingElection[]>([]);
  const [manageToken, setManageToken] = React.useState("");

  React.useEffect(() => {
    if (!token) {
      setPhase("error");
      setMessage("That link is missing its confirmation code.");
      return;
    }
    let live = true;
    confirm(token)
      .then((r) => {
        if (!live) return;
        setPostal(r.postal_code);
        setUpcoming(r.upcoming);
        setManageToken(r.manage_token);
        setPhase("done");
      })
      .catch((e) => {
        if (!live) return;
        setMessage(e.message || "That link is not valid.");
        setPhase("error");
      });
    return () => { live = false; };
  }, [token]);

  return (
    <div className="container" style={{ paddingTop: 28, paddingBottom: 48, maxWidth: 560 }}>
      {phase === "working" ? (
        <p className="t-body">Confirming your reminders…</p>
      ) : null}

      {phase === "done" ? (
        <div className="stack">
          <div className="confirm-mark"><Icon name="check" size={22} /></div>
          <h1 className="h-1">Reminders are on</h1>
          <p className="t-lead">
            We will email you a week before each election in{" "}
            <span className="mono">{postal}</span>, and again on the morning of
            the vote.
          </p>

          <div className="card" style={{ marginTop: 18 }}>
            <div className="section-label">What we will remind you about</div>
            <div style={{ marginTop: 10 }}>
              <UpcomingList elections={upcoming} />
            </div>
          </div>

          <div className="row row-gap-2" style={{ marginTop: 18 }}>
            <button className="act-btn primary" style={{ padding: 13, flex: 1 }}
              onClick={() => router.push(`/?postal=${encodeURIComponent(postal)}`)}>
              See who represents me
            </button>
            <button className="btn ghost"
              onClick={() => router.push(`/reminders/manage?token=${encodeURIComponent(manageToken)}`)}>
              Manage
            </button>
          </div>
        </div>
      ) : null}

      {phase === "error" ? (
        <div className="stack">
          <div className="err-mark"><Icon name="info" size={22} /></div>
          <h1 className="h-1">We could not confirm that</h1>
          <p className="t-lead">{message}</p>
          <p className="t-sm">
            Confirmation links stop working once a subscription has been
            cancelled. You can sign up again from any postal code lookup.
          </p>
          <button className="act-btn primary" style={{ padding: 13, marginTop: 14 }}
            onClick={() => router.push("/")}>
            Go to Parliament
          </button>
        </div>
      ) : null}
    </div>
  );
}

export default function ConfirmPage() {
  const router = useRouter();
  return (
    <>
      <header className="app-header">
        <div className="inner"><BrandMark onClick={() => router.push("/")} /></div>
      </header>
      <main>
        {/* useSearchParams needs a Suspense boundary to prerender. */}
        <React.Suspense fallback={<div className="container" style={{ paddingTop: 28 }}>
          <p className="t-body">Loading…</p></div>}>
          <ConfirmInner />
        </React.Suspense>
      </main>
    </>
  );
}
