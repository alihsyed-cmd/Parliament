import { getJurisdiction } from "@/lib/api";
import { JurisdictionRoster } from "@/components/JurisdictionRoster";

export const metadata = {
  title: "Federal · Parliament",
  description: "Browse all federal members of parliament and the federal cabinet.",
};

export default async function FederalPage() {
  const data = await getJurisdiction("ca_federal");
  return <JurisdictionRoster data={data} />;
}
