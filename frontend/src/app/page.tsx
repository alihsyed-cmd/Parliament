"use client";

/**
 * Parliament home page.
 *
 * Single postal-code input + submit. On valid submit, navigates to
 * /lookup/[postal_code] where results render. Validation is minimal —
 * format only — because the API has its own validation; we don't want
 * to duplicate it here.
 */

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";

const POSTAL_CODE_REGEX = /^[A-Z]\d[A-Z]\d[A-Z]\d$/;

function normalize(input: string): string {
  return input.replace(/\s+/g, "").toUpperCase();
}

export default function Home() {
  const router = useRouter();
  const [postalCode, setPostalCode] = useState("");
  const [error, setError] = useState<string | null>(null);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalized = normalize(postalCode);

    if (!POSTAL_CODE_REGEX.test(normalized)) {
      setError("Please enter a valid Canadian postal code (e.g., M5V 3L9).");
      return;
    }

    setError(null);
    router.push(`/lookup/${normalized}`);
  }

  return (
    <main className="min-h-screen flex items-center justify-center p-8">
      <div className="w-full max-w-md">
        <h1 className="text-5xl font-semibold tracking-tight mb-4">
          Meet your leaders.
        </h1>
        <p className="text-lg text-muted-foreground leading-relaxed mb-8">
          See your elected representatives at every level of government.
        </p>

        <form onSubmit={handleSubmit} noValidate>
          <label htmlFor="postal-code" className="block text-sm font-medium mb-2">
            Postal code
          </label>
          <input
            id="postal-code"
            type="text"
            value={postalCode}
            onChange={(e) => setPostalCode(e.target.value)}
            placeholder="M5V 3L9"
            autoComplete="postal-code"
            inputMode="text"
            maxLength={7}
            aria-invalid={error !== null}
            aria-describedby={error ? "postal-code-error" : undefined}
            className="w-full px-4 py-3 border rounded-md mb-2"
          />
          {error && (
            <p id="postal-code-error" className="text-sm text-red-600 mb-4" role="alert">
              {error}
            </p>
          )}
          <button
            type="submit"
            className="w-full px-4 py-3 bg-primary text-primary-foreground rounded-md font-medium hover:opacity-90 transition-opacity"
          >
            Find my representatives
          </button>
        </form>
      </div>
    </main>
  );
}
