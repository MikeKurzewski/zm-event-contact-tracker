import { ScoutDashboard } from "@/components/scout-dashboard";
import { loadDatasets } from "@/lib/targets";

export const dynamic = "force-static";

export default async function HomePage() {
  const datasets = await loadDatasets();

  return <ScoutDashboard datasets={datasets} />;
}
