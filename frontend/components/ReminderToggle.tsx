"use client";

import React from "react";
import { Icon } from "./Icon";
import { getReminder, saveReminder, clearReminder } from "@/lib/reminders";

export function ReminderToggle({ postalCode }: { postalCode: string }) {
  const [on, setOn] = React.useState(false);

  React.useEffect(() => {
    const r = getReminder();
    setOn(!!r?.enabled && r.postalCode === postalCode);
  }, [postalCode]);

  const toggle = () => {
    if (on) { clearReminder(); setOn(false); }
    else { saveReminder(postalCode); setOn(true); }
  };

  return (
    <div className={`reminder ${on ? "on" : ""}`}>
      <div className="row row-gap-3 between">
        <div className="row row-gap-3" style={{ alignItems: "flex-start" }}>
          <div style={{ width: 38, height: 38, borderRadius: 10, background: "var(--paper)", border: "1px solid var(--line)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, color: "var(--accent-ink)" }}>
            <Icon name="bell" size={18} />
          </div>
          <div>
            <div className="h-3" style={{ fontSize: 17 }}>Remind me before elections</div>
            <p className="t-sm" style={{ marginTop: 3 }}>
              We&apos;ll send a heads-up as each election approaches — municipal, provincial, and federal.
            </p>
          </div>
        </div>
        <button
          type="button"
          className={`switch ${on ? "on" : ""}`}
          role="switch"
          aria-checked={on}
          aria-label="Toggle election reminders"
          onClick={toggle}
        >
          <span className="knob" />
        </button>
      </div>
      {on ? (
        <p className="t-xs" style={{ marginTop: 12 }}>
          Saved on this device. Notifications turn on when you install the Parliament app.
        </p>
      ) : null}
    </div>
  );
}
