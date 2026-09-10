"use client";

// app/reminders/manage/page.tsx — the second link in every reminder footer.
//
// Shows what a subscription is set to, lets the postal code be changed, and
// offers the way out. The manage token from the email is the only credential,
// which is why the address is shown masked: this URL survives in inboxes and
// gets forwarded, and it should not print someone's full address to whoever
// opens it.

import React from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  getSubscription, unsubscribe, updatePostalCode,
  type SubscriptionInfo, type UpcomingElection,
} from "@/lib/reminders";
import { UpcomingList } from "@/components/ReminderToggle";
import { isValidPostalCode, normalizePostalCode, formatPostalCode } from "@/lib/api";
import { BrandMark } from "@/components/ui";
import { Icon } from "@/components/Icon";

function ManageInner() {
  const router = useRouter();
  const params = useSearchParams();
  const token = params.get("token") ?? "";

  const [loading, setLoading] = React.useState(true);
  const [sub, setSub] = React.useState<SubscriptionInfo | null>(null);
  const [upcoming, setUpcoming] = React.useState<UpcomingElection[]>([]);
  const [error, setError] = React.useState<string | null>(null);

  const [editing, setEditing] = React.useState(false);
  const [postal, setPostal] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [notice, setNotice] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!token) { setError("That link is missing its code."); setLoading(false); return; }
    let live = true;
    getSubscription(token)
      .then((r) => {
        if (!live) return;
        setSub(r);
        setUpcoming(r.upcoming);
        setPostal(formatPostalCode(r.postal_code));
      })
      .catch((e) => { if (live) setError((e as Error).message || "That link is not valid."); })
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [token]);

  const save = async () => {
    const code = normalizePostalCode(postal);
    if (!isValidPostalCode(code)) {
      setNotice("Enter a Canadian postal code, like K1A 0B1.");
      return;
    }
    setBusy(true);
    setNotice(null);
    try {
      const r = await updatePostalCode(token, code);
      setSub((s) => (s ? { ...s, postal_code: r.postal_code } : s));
      setUpcoming(r.upcoming);
      setEditing(false);
      setNotice("Saved. Your reminders now follow that postal code.");
    } catch (e) {
      setNotice((e as Error).message || "Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  const stop = async () => {
    setBusy(true);
    try {
      await unsubscribe(token);
      setSub((s) => (s ? { ...s, status: "unsubscribed" } : s));
      setUpcoming([]);
      setNotice(null);
    } catch (e) {
      setNotice((e as Error).message || "Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return <div className="container" style={{ paddingTop: 28 }}><p className="t-body">Loading…</p></div>;
  }

  if (error || !sub) {
    return (
      <div className="container" style={{ paddingTop: 28, maxWidth: 560 }}>
        <div className="stack">
          <div className="err-mark"><Icon name="info" size={22} /></div>
          <h1 className="h-1">That link is not valid</h1>
          <p className="t-lead">{error}</p>
          <button className="act-btn primary" style={{ padding: 13, marginTop: 14 }}
            onClick={() => router.push("/")}>Go to Parliament</button>
        </div>
      </div>
    );
  }

  return (
    <div className="container" style={{ paddingTop: 28, paddingBottom: 48, maxWidth: 560 }}>
      <h1 className="h-1">Your election reminders</h1>

      <div className="card" style={{ marginTop: 18 }}>
        <div className="row between row-gap-3">
          <div>
            <div className="section-label">Email</div>
            <div className="t-body mono" style={{ marginTop: 2 }}>{sub.email}</div>
          </div>
          <div className="pill">
            {sub.status === "active" ? "On"
              : sub.status === "pending" ? "Not confirmed"
              : sub.status === "unsubscribed" ? "Off"
              : "Stopped"}
          </div>
        </div>

        <div className="divider" style={{ margin: "14px 0" }} />

        <div className="section-label">Postal code</div>
        {editing ? (
          <div style={{ marginTop: 6 }}>
            <div className="field">
              <input value={postal} onChange={(e) => setPostal(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") save(); }}
                placeholder="K1A 0B1" aria-label="Postal code" />
            </div>
            <div className="row row-gap-2" style={{ marginTop: 10 }}>
              <button className="act-btn primary" style={{ padding: 11 }}
                onClick={save} disabled={busy}>{busy ? "Saving…" : "Save"}</button>
              <button className="btn ghost" onClick={() => {
                setEditing(false);
                setPostal(formatPostalCode(sub.postal_code));
                setNotice(null);
              }}>Cancel</button>
            </div>
          </div>
        ) : (
          <div className="row between row-gap-3" style={{ marginTop: 2 }}>
            <div className="t-body mono">{formatPostalCode(sub.postal_code)}</div>
            {sub.status === "active" || sub.status === "pending" ? (
              <button className="btn ghost" onClick={() => setEditing(true)}>Change</button>
            ) : null}
          </div>
        )}
      </div>

      {notice ? <p className="t-sm" style={{ marginTop: 12 }} role="status">{notice}</p> : null}

      {sub.status === "pending" ? (
        <p className="t-sm" style={{ marginTop: 18 }}>
          This subscription is not confirmed yet. Open the link in the
          confirmation email and reminders will start.
        </p>
      ) : null}

      {sub.status === "active" ? (
        <div className="card" style={{ marginTop: 18 }}>
          <div className="section-label">What we will remind you about</div>
          <div style={{ marginTop: 10 }}><UpcomingList elections={upcoming} /></div>
          <p className="t-xs" style={{ marginTop: 12 }}>
            One email a week before each, one on the morning of the vote.
          </p>
        </div>
      ) : null}

      {sub.status === "active" || sub.status === "pending" ? (
        <button className="btn ghost" style={{ marginTop: 22 }} onClick={stop} disabled={busy}>
          Stop these reminders
        </button>
      ) : (
        <p className="t-sm" style={{ marginTop: 22 }}>
          Reminders are off for this address. You can start again from any postal
          code lookup.
        </p>
      )}
    </div>
  );
}

export default function ManagePage() {
  const router = useRouter();
  return (
    <>
      <header className="app-header">
        <div className="inner"><BrandMark onClick={() => router.push("/")} /></div>
      </header>
      <main>
        <React.Suspense fallback={<div className="container" style={{ paddingTop: 28 }}>
          <p className="t-body">Loading…</p></div>}>
          <ManageInner />
        </React.Suspense>
      </main>
    </>
  );
}
