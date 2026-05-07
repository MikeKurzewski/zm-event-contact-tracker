import { notFound } from "next/navigation";

import { ScoutDashboard } from "@/components/scout-dashboard";
import { loadEvent, loadEvents } from "@/lib/targets";

export const dynamic = "force-static";

type PageProps = {
  params: Promise<{
    eventSlug: string;
  }>;
};

export async function generateStaticParams() {
  const events = await loadEvents();
  return events.map((event) => ({
    eventSlug: event.slug
  }));
}

export default async function EventPage({ params }: PageProps) {
  const { eventSlug } = await params;
  const event = await loadEvent(eventSlug);

  if (!event) {
    notFound();
  }

  return <ScoutDashboard event={event} datasets={event.datasets} />;
}
