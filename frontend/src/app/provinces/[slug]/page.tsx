import { getJurisdiction, ApiError } from "@/lib/api";
import { JurisdictionRoster } from "@/components/JurisdictionRoster";
import { notFound } from "next/navigation";

type PageProps = {
  params: Promise<{ slug: string }>;
};

export async function generateMetadata({ params }: PageProps) {
  const { slug } = await params;
  try {
    const data = await getJurisdiction(slug);
    return {
      title: `${data.jurisdiction.name} · Parliament`,
      description: `Members of provincial parliament and cabinet for ${data.jurisdiction.name}.`,
    };
  } catch {
    return { title: "Not found · Parliament" };
  }
}

export default async function ProvinceDetailPage({ params }: PageProps) {
  const { slug } = await params;
  try {
    const data = await getJurisdiction(slug);
    if (data.jurisdiction.level !== "provincial") {
      notFound();
    }
    return <JurisdictionRoster data={data} />;
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      notFound();
    }
    throw err;
  }
}
