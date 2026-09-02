"use client";

// app/claim/page.tsx — the one door in for candidates. No candidate is emailed
// a link unprompted, so this URL is what outreach prints and says aloud; keep
// it stable.

import React from "react";
import { useRouter } from "next/navigation";
import type { ClaimInfo } from "@/lib/candidate-types";
import { SUBMISSIONS_ENABLED, candidateApi } from "@/lib/candidates";
import {
  ClaimChallengeScreen, ClaimSearchScreen, ClaimSentScreen, ClaimUnavailable,
} from "@/components/ClaimScreens";
import { ContactPage } from "@/components/StaticPages";
import { BrandMark } from "@/components/ui";
import { Icon } from "@/components/Icon";

type Step = "search" | "challenge" | "sent" | "unavailable" | "contact";

export default function ClaimPage() {
  const router = useRouter();
  const [step, setStep] = React.useState<Step>("search");
  const [uuid, setUuid] = React.useState<string | null>(null);
  const [info, setInfo] = React.useState<ClaimInfo | null>(null);
  const [typed, setTyped] = React.useState("");

  const pick = async (id: string) => {
    setUuid(id);
    setInfo(null);
    setStep("challenge");
    try {
      setInfo(await candidateApi.claimInfo(id));
    } catch {
      setInfo(null); // fall back to local row shape
    }
  };

  const back = () => {
    if (step === "search") { router.push("/"); return; }
    setStep(step === "challenge" ? "search" : "challenge");
  };

  return (
    <>
      <header className="app-header">
        <div className="inner">
          <div className="row row-gap-3">
            <button className="btn ghost icon-only" onClick={back} aria-label="Back">
              <Icon name="arrow_left" size={20} />
            </button>
            <BrandMark onClick={() => router.push("/")} />
          </div>
        </div>
      </header>
      <main key={step}>
        {step === "search" ? <ClaimSearchScreen onPick={pick} /> : null}
        {step === "challenge" && uuid ? (
          <ClaimChallengeScreen
            uuid={uuid} info={info}
            onSent={(t) => { setTyped(t); setStep(SUBMISSIONS_ENABLED ? "sent" : "unavailable"); }}
            onContact={() => setStep("contact")}
          />
        ) : null}
        {step === "sent" ? <ClaimSentScreen typed={typed} onContact={() => setStep("contact")} /> : null}
        {step === "unavailable" ? <ClaimUnavailable onBack={() => setStep("search")} /> : null}
        {step === "contact" ? <ContactPage candidateUuid={uuid} reason="claim" /> : null}
      </main>
    </>
  );
}
