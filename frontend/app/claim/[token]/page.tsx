"use client";

// app/claim/<token>/page.tsx — the emailed link lands HERE, on our own origin,
// and posts the token to /claim/exchange same-site. A cross-domain redirect
// straight to the API would drop the session cookie in most browsers.
//
// The token is durable and multi-use through election day: exchanging it does
// not consume it, so the same link works tomorrow.

import React from "react";
import { useParams, useRouter } from "next/navigation";
import { candidateApi } from "@/lib/candidates";
import { ClaimTokenInvalid } from "@/components/ClaimScreens";
import { ManageProfileScreen } from "@/components/ManageScreen";
import { BrandMark } from "@/components/ui";

export default function ClaimTokenPage() {
  const params = useParams<{ token: string }>();
  const router = useRouter();
  const [state, setState] = React.useState<"exchanging" | "ok" | "invalid">("exchanging");
  const [uuid, setUuid] = React.useState<string | null>(null);

  React.useEffect(() => {
    const token = Array.isArray(params?.token) ? params.token[0] : params?.token;
    if (!token) { setState("invalid"); return; }
    let live = true;
    candidateApi.exchange(token)
      .then((r) => { if (live) { setUuid(r.candidate_uuid); setState("ok"); } })
      // 400 invalid_token covers expired, forged and malformed alike — the API
      // does not distinguish them, so neither does the screen.
      .catch(() => { if (live) setState("invalid"); });
    return () => { live = false; };
  }, [params]);

  return (
    <>
      <header className="app-header">
        <div className="inner">
          <BrandMark onClick={() => router.push("/")} />
        </div>
      </header>
      <main>
        {state === "exchanging" ? (
          <div className="container fade-in" style={{ maxWidth: 480, textAlign: "center" }}>
            <div className="spin" />
            <p className="t-lead" style={{ marginTop: 18 }}>Opening your page…</p>
          </div>
        ) : null}
        {state === "invalid" ? <ClaimTokenInvalid onSearch={() => router.push("/claim")} /> : null}
        {state === "ok" && uuid ? (
          <ManageProfileScreen uuid={uuid} onDone={() => router.push("/")} />
        ) : null}
      </main>
    </>
  );
}
