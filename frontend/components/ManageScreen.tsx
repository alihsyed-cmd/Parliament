"use client";

// components/ManageScreen.tsx — the candidate portal (#4) and the two upload
// states (#5). Reached only after /claim/exchange has set the session cookie.
//
// Upload loop: POST /candidates/<uuid>/upload-url → POST the file DIRECT to
// Cloudflare → the backend receives the ready/failed webhook and promotes or
// reverts. We never handle bytes and never poll for processing: the outcome
// arrives at the backend, not here, so the claimant is free to leave.

import React from "react";
import type { PortalInfo } from "@/lib/candidate-types";
import { candidateApi } from "@/lib/candidates";
import { Icon } from "./Icon";

/** Transfer in flight — leaving now aborts it, so this does NOT say you may go. */
function VideoUploading({ stage }: { stage: "requesting" | "uploading" }) {
  return (
    <div className="container fade-in" style={{ maxWidth: 480, textAlign: "center" }}>
      <div className="spin" />
      <h1 className="h-1" style={{ marginTop: 20 }}>Uploading</h1>
      <p className="t-lead" style={{ marginTop: 10 }}>
        {stage === "requesting" ? "Preparing your upload…" : "Uploading your video…"}
      </p>
      <p className="t-sm" style={{ marginTop: 16, color: "var(--ink-3)" }}>
        Keep this page open until the upload finishes.
      </p>
    </div>
  );
}

/** Terminal for this session. The transfer is done and the backend owns the
 *  outcome from here, so this must not auto-advance to a thumbnail — we cannot
 *  know whether encoding succeeded. A later load reads real state. */
function VideoProcessing({ onDone }: { onDone: () => void }) {
  return (
    <div className="container fade-in" style={{ maxWidth: 480, textAlign: "center" }}>
      <div className="spin" />
      <h1 className="h-1" style={{ marginTop: 20 }}>Upload complete</h1>
      <p className="t-lead" style={{ marginTop: 10 }}>
        We&apos;re processing your video — usually a minute or two.
      </p>
      <p className="t-sm" style={{ marginTop: 16, color: "var(--ink-3)" }}>
        You can close this page. Your profile updates on its own once it&apos;s ready — no need to
        wait here.
      </p>
      <button type="button" className="act-btn" style={{ padding: 13, marginTop: 20, width: "100%" }} onClick={onDone}>
        Back to my page
      </button>
    </div>
  );
}

/** Transfer-level failure — the only class this code can observe. */
function VideoFailed({ onRetry, onBack }: { onRetry: () => void; onBack: () => void }) {
  return (
    <div className="container fade-in" style={{ maxWidth: 480, textAlign: "center" }}>
      <div className="err-mark"><Icon name="info" size={22} /></div>
      <h1 className="h-1" style={{ marginTop: 18, fontSize: 30 }}>We couldn&apos;t process that video</h1>
      <p className="t-lead" style={{ marginTop: 10 }}>
        This sometimes happens with unusual file formats or a dropped connection.
      </p>
      <button type="button" className="act-btn primary" style={{ padding: 14, marginTop: 18, width: "100%" }} onClick={onRetry}>
        Try uploading again
      </button>
      <p className="t-xs" style={{ marginTop: 12 }}>Your page stays exactly as it was before this upload.</p>
      <button type="button" className="act-btn" style={{ padding: 13, marginTop: 14, width: "100%" }} onClick={onBack}>
        Back to my page
      </button>
    </div>
  );
}

type Phase = "loading" | "idle" | "requesting" | "uploading" | "processing" | "failed" | "error";

export function ManageProfileScreen({ uuid, onDone }: { uuid: string; onDone: () => void }) {
  const [portal, setPortal] = React.useState<PortalInfo | null>(null);
  const [phase, setPhase] = React.useState<Phase>("loading");
  const [website, setWebsite] = React.useState("");
  const [saving, setSaving] = React.useState(false);
  const [confirmRemove, setConfirmRemove] = React.useState(false);
  const fileRef = React.useRef<HTMLInputElement>(null);

  const load = React.useCallback(async () => {
    try {
      const p = await candidateApi.portal(uuid);
      setPortal(p);
      setWebsite(p.website ?? "");
      setPhase("idle");
    } catch {
      setPhase("error");
    }
  }, [uuid]);

  React.useEffect(() => { load(); }, [load]);

  const startUpload = async (file?: File) => {
    if (!file) return;
    setPhase("requesting");
    try {
      const { upload_url } = await candidateApi.uploadUrl(uuid);
      setPhase("uploading");
      await candidateApi.uploadToCloudflare(upload_url, file);
      // Transfer done. Outcome is the webhook's to deliver, not ours to poll.
      setPhase("processing");
    } catch {
      setPhase("failed"); // prior state untouched, so the revert copy is literally true
    }
  };

  const save = async () => {
    setSaving(true);
    try {
      await candidateApi.saveWebsite(uuid, website.trim());
      onDone();
    } catch {
      setSaving(false);
    }
  };

  const removeVideo = async () => {
    setConfirmRemove(false);
    try {
      setPortal(await candidateApi.removeVideo(uuid));
    } catch { /* leave the screen as-is; nothing was changed */ }
  };

  if (phase === "requesting" || phase === "uploading") return <VideoUploading stage={phase} />;
  if (phase === "processing") return <VideoProcessing onDone={onDone} />;
  if (phase === "failed") {
    return <VideoFailed onRetry={() => { setPhase("idle"); fileRef.current?.click(); }} onBack={() => setPhase("idle")} />;
  }
  if (phase === "loading") {
    return (
      <div className="container fade-in" style={{ maxWidth: 480, textAlign: "center" }}>
        <div className="spin" />
      </div>
    );
  }
  if (phase === "error" || !portal) {
    return (
      <div className="container fade-in" style={{ maxWidth: 480, textAlign: "center" }}>
        <div className="err-mark"><Icon name="info" size={22} /></div>
        <h1 className="h-1" style={{ marginTop: 18, fontSize: 30 }}>We couldn&apos;t open your page</h1>
        <p className="t-lead" style={{ marginTop: 10 }}>
          Your editing session may have ended. Open your link again to continue.
        </p>
      </div>
    );
  }

  const where = [portal.district || portal.office, portal.jurisdiction].filter(Boolean).join(", ");

  return (
    <div className="container fade-in" style={{ maxWidth: 560 }}>
      <div className="stack stack-3" style={{ marginBottom: 22 }}>
        <div className="eyebrow accent">Manage this page</div>
        <h1 className="h-1" style={{ fontSize: 32 }}>{portal.name}</h1>
        <p className="t-lead">{where}</p>
      </div>

      <div style={{ marginBottom: 22 }}>
        <div className="field-label">Pitch video</div>

        {portal.pending && portal.has_video ? (
          <div className="card ghost" style={{ padding: 14, marginBottom: 10 }}>
            <p className="t-sm" style={{ margin: 0, lineHeight: 1.5 }}>
              Your replacement is still processing. Voters keep seeing your current video until it&apos;s ready.
            </p>
          </div>
        ) : null}

        {portal.video_status === "processing" && !portal.has_video ? (
          <div className="card ghost" style={{ padding: 14, marginBottom: 10 }}>
            <p className="t-sm" style={{ margin: 0, lineHeight: 1.5 }}>
              Your video is still processing. It appears on your page on its own once it&apos;s ready.
            </p>
          </div>
        ) : null}

        {portal.video_status === "failed" ? (
          <div className="card ghost" style={{ padding: 14, marginBottom: 10 }}>
            <p className="t-sm" style={{ margin: 0, lineHeight: 1.5 }}>
              Your last upload didn&apos;t process. Nothing changed on your page — you can try again below.
            </p>
          </div>
        ) : null}

        {portal.has_video ? (
          <>
            <div className="vid-thumb">
              {portal.thumbnail_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={portal.thumbnail_url} alt=""
                  onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />
              ) : null}
              <div className="play"><span><Icon name="play" size={15} /></span></div>
            </div>
            <div className="act-row" style={{ marginTop: 10 }}>
              <button type="button" className="act-btn" onClick={() => fileRef.current?.click()}>Replace video</button>
              <button type="button" className="act-btn muted" onClick={() => setConfirmRemove(true)}>Remove video</button>
            </div>
            {confirmRemove ? (
              <div className="card ghost" style={{ padding: 14, marginTop: 10 }}>
                <p className="t-sm" style={{ margin: 0, lineHeight: 1.5 }}>
                  Remove your video? Your page stays listed either way — you can upload a new one any time.
                </p>
                <div className="act-row" style={{ marginTop: 12 }}>
                  <button type="button" className="act-btn" onClick={removeVideo}>Remove it</button>
                  <button type="button" className="act-btn muted" onClick={() => setConfirmRemove(false)}>Keep it</button>
                </div>
              </div>
            ) : null}
          </>
        ) : (
          <button type="button" className="upload-drop" onClick={() => fileRef.current?.click()}>
            <span className="ic"><Icon name="play" size={16} /></span>
            <span className="t-body" style={{ fontWeight: 500 }}>Upload a pitch video</span>
            <span className="t-xs">Up to 60 seconds. Record it however you like.</span>
          </button>
        )}

        <input ref={fileRef} type="file" accept="video/*" style={{ display: "none" }}
          onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; startUpload(f); }} />
      </div>

      <div style={{ marginBottom: 22 }}>
        <div className="field-label">Website</div>
        <div className="field">
          <input value={website} onChange={(e) => setWebsite(e.target.value)}
            placeholder="yourcampaign.ca" aria-label="Campaign website" />
        </div>
        <p className="t-xs" style={{ marginTop: 7 }}>
          Publishes right away, whether or not you add a video.
        </p>
      </div>

      <button type="button" className="act-btn primary" style={{ padding: 14, width: "100%" }} onClick={save} disabled={saving}>
        {saving ? "Saving…" : "Save changes"}
      </button>
      <p className="t-xs" style={{ textAlign: "center", marginTop: 12 }}>
        You can come back and edit this any time before October 26 using the same link.
      </p>
    </div>
  );
}
