/**
 * Empty-state message shown when a jurisdiction level has no data
 * for the user's location (e.g., Quebec province, Vancouver municipal).
 *
 * Intentionally informative rather than apologetic — Parliament is
 * actively expanding coverage, and this message is the only visible
 * promise of it.
 */

type CoverageGapProps = {
  level: "municipal" | "provincial" | "federal";
};

const LEVEL_LABEL: Record<CoverageGapProps["level"], string> = {
  municipal: "municipal",
  provincial: "provincial",
  federal: "federal",
};

export function CoverageGap({ level }: CoverageGapProps) {
  return (
    <div className="border border-dashed border-gray-300 rounded-md p-6 text-center">
      <p className="text-sm text-gray-600">
        Coverage coming soon — your {LEVEL_LABEL[level]} representatives
        will appear here.
      </p>
    </div>
  );
}
