import { listJurisdictions } from "@/lib/api";
import { JurisdictionListItem } from "@/components/JurisdictionListItem";

export const metadata = {
  title: "Municipalities · Parliament",
  description: "Browse city councillors and mayors across registered Canadian municipalities.",
};

export default async function MunicipalitiesPage() {
  const data = await listJurisdictions();
  const municipalities = data.jurisdictions.filter((j) => j.level === "municipal");

  return (
    <main className="min-h-screen px-6 py-12 max-w-3xl mx-auto">
      <header className="mb-12">
        <h1 className="text-3xl font-semibold tracking-tight mb-2">Municipalities</h1>
        <p className="text-muted-foreground">
          Cities with registered councillor and mayor data.
        </p>
      </header>

      {municipalities.length === 0 ? (
        <p className="text-muted-foreground">No municipalities registered yet.</p>
      ) : (
        <div className="grid gap-3">
          {municipalities.map((j) => (
            <JurisdictionListItem key={j.slug} jurisdiction={j} />
          ))}
        </div>
      )}
    </main>
  );
}
