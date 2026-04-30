import { listJurisdictions } from "@/lib/api";
import { JurisdictionListItem } from "@/components/JurisdictionListItem";

export const metadata = {
  title: "Provinces · Parliament",
  description: "Browse provincial members of parliament and cabinets across registered provinces.",
};

export default async function ProvincesPage() {
  const data = await listJurisdictions();
  const provinces = data.jurisdictions.filter((j) => j.level === "provincial");

  return (
    <main className="min-h-screen px-6 py-12 max-w-3xl mx-auto">
      <header className="mb-12">
        <h1 className="text-3xl font-semibold tracking-tight mb-2">Provinces</h1>
        <p className="text-muted-foreground">
          Provinces with registered MPP and cabinet data.
        </p>
      </header>

      {provinces.length === 0 ? (
        <p className="text-muted-foreground">No provinces registered yet.</p>
      ) : (
        <div className="grid gap-3">
          {provinces.map((j) => (
            <JurisdictionListItem key={j.slug} jurisdiction={j} />
          ))}
        </div>
      )}
    </main>
  );
}
