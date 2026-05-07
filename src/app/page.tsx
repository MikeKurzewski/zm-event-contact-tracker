import Link from "next/link";

import { ArrowRight, CalendarDays } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle
} from "@/components/ui/card";
import { loadEvents } from "@/lib/targets";

export const dynamic = "force-static";

export default async function HomePage() {
  const events = await loadEvents();

  return (
    <main className="min-h-screen bg-background">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-8 px-4 py-8 md:px-6 md:py-10">
        <section className="flex flex-col gap-3">
          <p className="text-xs font-semibold uppercase tracking-[0.28em] text-muted-foreground">
            Event Scout
          </p>
          <h1 className="max-w-3xl break-words text-3xl font-semibold tracking-tight md:text-4xl">
            Choose an event dashboard
          </h1>
          <p className="max-w-3xl break-words text-sm leading-7 text-muted-foreground">
            Each event reads its own generated CSV outputs from the matching folder in the repo.
          </p>
        </section>

        <section className="grid gap-4 md:grid-cols-2">
          {events.map((event) => (
            <Link
              key={event.slug}
              href={`/events/${event.slug}`}
              className="group block rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <Card className="h-full border-border bg-card shadow-sm transition-colors group-hover:bg-accent/50">
                <CardHeader className="gap-3">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex size-11 shrink-0 items-center justify-center rounded-md bg-secondary text-secondary-foreground">
                      <CalendarDays className="size-5" />
                    </div>
                    <ArrowRight className="mt-2 size-5 text-muted-foreground transition-transform group-hover:translate-x-1" />
                  </div>
                  <div className="flex flex-col gap-2">
                    <CardTitle className="break-words text-2xl tracking-tight">{event.name}</CardTitle>
                    <CardDescription className="break-words text-sm leading-6">
                      {event.description || `${event.datasets.length} CSV datasets available for this event.`}
                    </CardDescription>
                  </div>
                </CardHeader>
                <CardContent className="flex flex-wrap gap-2">
                  <Badge variant="secondary">{event.totalTargets} targets</Badge>
                  <Badge variant="outline">{event.datasets.length} datasets</Badge>
                  {event.updatedAt ? (
                    <Badge variant="outline">
                      Updated {new Intl.DateTimeFormat("en", { dateStyle: "medium" }).format(new Date(event.updatedAt))}
                    </Badge>
                  ) : null}
                </CardContent>
              </Card>
            </Link>
          ))}
        </section>

        {!events.length ? (
          <Card className="border-dashed border-border bg-card">
            <CardContent className="p-8 text-sm text-muted-foreground">
              No event folders found. Run the scraper with an event slug to create the first dashboard.
            </CardContent>
          </Card>
        ) : null}
      </div>
    </main>
  );
}
