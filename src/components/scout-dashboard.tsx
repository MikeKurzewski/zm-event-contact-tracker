"use client";

import { useDeferredValue, useEffect, useState } from "react";
import {
  Building2,
  ExternalLink,
  Factory,
  Filter,
  Handshake,
  MapPin,
  Search,
  Star
} from "lucide-react";

import type { DatasetKey, DatasetSummary, ScoutTarget } from "@/lib/targets";
import { cn, humanizeLabel } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle
} from "@/components/ui/sheet";

type Props = {
  datasets: DatasetSummary[];
};

function datasetIcon(key: DatasetKey) {
  if (key === "priority") return Star;
  if (key === "manufacturers") return Factory;
  if (key === "partners") return Handshake;
  if (key === "crm") return Building2;
  return Filter;
}

function badgeTone(target: ScoutTarget) {
  if (target.confidence === "high") return "default";
  if (target.confidence === "medium") return "secondary";
  if (target.score !== null && target.score >= 36) return "default";
  if (target.score !== null && target.score >= 26) return "secondary";
  return "outline";
}

function geoLabel(bucket: string) {
  if (!bucket) return "";
  return bucket.replace("priority_", "").replace(/_/g, " ");
}

function targetMatchesSearch(target: ScoutTarget, query: string) {
  if (!query) return true;
  const haystack = [
    target.companyName,
    target.country,
    target.booth,
    target.targetType,
    target.overview,
    target.websiteLabel,
    target.crmCompanyName,
    target.crmIndustry,
    target.crmProduct
  ]
    .join(" ")
    .toLowerCase();

  return haystack.includes(query.toLowerCase());
}

function DetailSection({
  label,
  value
}: {
  label: string;
  value: string;
}) {
  if (!value) return null;
  return (
    <div className="flex flex-col gap-1">
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
        {label}
      </p>
      <p className="text-sm leading-6 text-foreground">{value}</p>
    </div>
  );
}

function TargetDetail({ target }: { target: ScoutTarget | null }) {
  if (!target) {
    return (
      <Card className="border-border bg-card shadow-sm">
        <CardHeader>
          <CardTitle>Select a company</CardTitle>
          <CardDescription>
            Choose a target from the list to see booth details, scoring signals, and links.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <Card className="border-border bg-card shadow-sm">
      <CardHeader className="flex flex-col gap-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex flex-col gap-2">
            <CardTitle className="text-2xl tracking-tight">{target.companyName}</CardTitle>
            <CardDescription className="max-w-xl text-sm leading-6">
              {target.overview || "No summary available."}
            </CardDescription>
          </div>
          <div className="flex flex-wrap gap-2">
            {target.score !== null ? (
              <Badge variant={badgeTone(target)}>Score {target.score}</Badge>
            ) : null}
            {target.targetType ? <Badge variant="outline">{humanizeLabel(target.targetType)}</Badge> : null}
            {target.confidence ? <Badge variant={badgeTone(target)}>{humanizeLabel(target.confidence)}</Badge> : null}
          </div>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-6">
        <div className="grid gap-4 md:grid-cols-2">
          <DetailSection label="Booth" value={target.booth} />
          <DetailSection label="Country" value={target.country} />
          <DetailSection label="Country Priority" value={geoLabel(target.countryPriority)} />
          <DetailSection label="Category" value={humanizeLabel(target.category || target.targetType)} />
        </div>

        <Separator />

        <div className="grid gap-5">
          <DetailSection label="Recommended Angle" value={target.outreachAngle} />
          <DetailSection label="Official Hannover Overview" value={target.officialOverview} />
          <DetailSection label="Company Website Overview" value={target.companySiteHome} />
          <DetailSection label="About / Company Page" value={target.companySiteAbout} />
          <DetailSection label="Matched Keywords" value={target.matchedKeywords.join(", ")} />
          <DetailSection label="Negative Keywords" value={target.negativeKeywords.join(", ")} />
          <DetailSection
            label="CRM Context"
            value={[target.crmSource, target.crmListName, target.crmIndustry, target.crmProduct]
              .filter(Boolean)
              .join(" | ")}
          />
          <DetailSection label="CRM Match Reason" value={target.matchReason} />
        </div>
      </CardContent>
      <CardFooter className="flex flex-wrap gap-3">
        {target.website ? (
          <Button asChild>
            <a href={target.website} rel="noreferrer" target="_blank">
              <ExternalLink data-icon="inline-end" />
              Company Website
            </a>
          </Button>
        ) : null}
        {target.profileUrl ? (
          <Button asChild variant="outline">
            <a href={target.profileUrl} rel="noreferrer" target="_blank">
              <ExternalLink data-icon="inline-end" />
              Hannover Profile
            </a>
          </Button>
        ) : null}
        {target.crmCardUrl ? (
          <Button asChild variant="secondary">
            <a href={target.crmCardUrl} rel="noreferrer" target="_blank">
              <ExternalLink data-icon="inline-end" />
              CRM Card
            </a>
          </Button>
        ) : null}
      </CardFooter>
    </Card>
  );
}

export function ScoutDashboard({ datasets }: Props) {
  const [activeDataset, setActiveDataset] = useState<DatasetKey>("priority");
  const [selectedId, setSelectedId] = useState<string>("");
  const [query, setQuery] = useState("");
  const [mobileOpen, setMobileOpen] = useState(false);
  const deferredQuery = useDeferredValue(query);

  const active = datasets.find((dataset) => dataset.key === activeDataset) ?? datasets[0];
  const filteredTargets = active.targets.filter((target) => targetMatchesSearch(target, deferredQuery));
  const selectedTarget =
    filteredTargets.find((target) => target.id === selectedId) ??
    active.targets.find((target) => target.id === selectedId) ??
    filteredTargets[0] ??
    null;

  useEffect(() => {
    if (!selectedTarget && active.targets[0]) {
      setSelectedId(active.targets[0].id);
      return;
    }
    if (selectedTarget && selectedTarget.id !== selectedId) {
      setSelectedId(selectedTarget.id);
    }
  }, [active.targets, selectedId, selectedTarget]);

  return (
    <div className="min-h-screen bg-background">
      <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-8 px-4 py-6 md:px-8 md:py-8">
        <Card className="overflow-hidden border-border bg-card shadow-sm">
          <CardHeader className="gap-5">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
              <div className="flex max-w-3xl flex-col gap-3">
                <CardDescription className="text-xs font-semibold uppercase tracking-[0.28em] text-muted-foreground">
                  Hannover Messe Scout
                </CardDescription>
                <CardTitle className="text-3xl tracking-tight md:text-4xl">
                  CSV-driven scouting dashboard for booth-side outreach
                </CardTitle>
                <p className="text-sm leading-7 text-muted-foreground">
                  The app reads the generated CSV outputs directly from the repo and surfaces booth numbers,
                  scoring, target type, and company context in a clean mobile-friendly layout.
                </p>
              </div>
              <div className="grid min-w-[280px] gap-3 sm:grid-cols-3">
                {datasets.slice(0, 3).map((dataset) => {
                  const Icon = datasetIcon(dataset.key);
                  return (
                    <Card key={dataset.key} className="border-border bg-muted/40 shadow-none">
                      <CardContent className="flex items-center gap-3 p-4">
                        <div className="flex size-10 items-center justify-center rounded-full bg-secondary text-secondary-foreground">
                          <Icon className="size-5" />
                        </div>
                        <div className="flex flex-col">
                          <span className="text-xs uppercase tracking-[0.18em] text-muted-foreground">
                            {dataset.label}
                          </span>
                          <span className="text-lg font-semibold">{dataset.targets.length}</span>
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            </div>
          </CardHeader>
        </Card>

        <div className="grid gap-8 xl:grid-cols-[minmax(0,0.92fr)_minmax(360px,0.78fr)]">
          <div className="flex flex-col gap-4">
            <Card className="border-border bg-card shadow-sm">
              <CardHeader className="gap-4">
                <div className="flex flex-wrap gap-2">
                  {datasets.map((dataset) => {
                    const Icon = datasetIcon(dataset.key);
                    return (
                      <Button
                        key={dataset.key}
                        onClick={() => {
                          setActiveDataset(dataset.key);
                          setQuery("");
                        }}
                        aria-pressed={dataset.key === activeDataset}
                        variant={dataset.key === activeDataset ? "default" : "outline"}
                        size="sm"
                        className="transition-colors"
                      >
                        <Icon data-icon="inline-start" />
                        {dataset.label}
                      </Button>
                    );
                  })}
                </div>
                <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                  <div className="flex flex-col gap-1">
                    <CardTitle>{active.label}</CardTitle>
                    <CardDescription>{active.description}</CardDescription>
                  </div>
                  <div className="relative w-full md:max-w-sm">
                    <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                    <Input
                      value={query}
                      onChange={(event) => setQuery(event.target.value)}
                      className="pl-9"
                      placeholder="Search company, booth, type, country..."
                    />
                  </div>
                </div>
              </CardHeader>
            </Card>

            <div className="grid gap-3">
              {filteredTargets.map((target) => (
                <button
                  key={target.id}
                  className={cn(
                    "cursor-pointer rounded-2xl border border-border bg-card p-4 text-left shadow-sm transition-colors hover:bg-accent/50",
                    selectedTarget?.id === target.id && "border-primary bg-accent"
                  )}
                  aria-pressed={selectedTarget?.id === target.id}
                  onClick={() => {
                    setSelectedId(target.id);
                    setMobileOpen(true);
                  }}
                  type="button"
                >
                  <div className="flex flex-col gap-3">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="flex min-w-0 flex-col gap-1">
                        <p className="truncate text-lg font-semibold tracking-tight">{target.companyName}</p>
                        <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
                          {target.booth ? (
                            <span className="inline-flex items-center gap-1.5">
                              <MapPin className="size-3.5" />
                              {target.booth}
                            </span>
                          ) : null}
                          {target.country ? <span>{target.country}</span> : null}
                        </div>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {target.score !== null ? (
                          <Badge variant={badgeTone(target)}>Score {target.score}</Badge>
                        ) : null}
                        {target.targetType ? (
                          <Badge variant="outline">{humanizeLabel(target.targetType)}</Badge>
                        ) : null}
                        {target.countryPriority ? (
                          <Badge variant="secondary">{geoLabel(target.countryPriority)}</Badge>
                        ) : null}
                      </div>
                    </div>
                    <p className="line-clamp-2 text-sm leading-6 text-muted-foreground">
                      {target.overview || "No summary available."}
                    </p>
                    <div className="flex flex-wrap items-center gap-3 text-xs uppercase tracking-[0.16em] text-muted-foreground">
                      {target.websiteLabel ? <span>{target.websiteLabel}</span> : null}
                      {target.crmSource ? <span>CRM {target.crmSource}</span> : null}
                      {target.confidence ? <span>{target.confidence} confidence</span> : null}
                    </div>
                    <div className="flex items-center justify-between gap-3 border-t border-border/60 pt-3">
                      <span className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                        Tap for details
                      </span>
                      <span className="rounded-full bg-secondary px-3 py-1 text-xs font-medium text-secondary-foreground">
                        {target.booth || "Open company card"}
                      </span>
                    </div>
                  </div>
                </button>
              ))}
              {!filteredTargets.length ? (
                <Card className="border-dashed border-border bg-card">
                  <CardContent className="flex flex-col gap-2 p-8 text-sm text-muted-foreground">
                    <p className="font-medium text-foreground">No matches for this search.</p>
                    <p>Try a company name, country, booth, or target type.</p>
                  </CardContent>
                </Card>
              ) : null}
            </div>
          </div>

          <div className="hidden xl:block">
            <div className="sticky top-6">
              <TargetDetail target={selectedTarget} />
            </div>
          </div>
        </div>
      </div>

      <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
        <SheetContent className="w-full overflow-y-auto sm:max-w-2xl xl:hidden">
          <SheetHeader>
            <SheetTitle>{selectedTarget?.companyName ?? "Target details"}</SheetTitle>
            <SheetDescription>
              Tap through booth details, scoring, and links while walking the show floor.
            </SheetDescription>
          </SheetHeader>
          <div className="mt-6">
            <TargetDetail target={selectedTarget} />
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}
