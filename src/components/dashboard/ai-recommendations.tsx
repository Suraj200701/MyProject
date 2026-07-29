import { ArrowUpRight, Sparkles } from "lucide-react";
import Link from "next/link";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";

const recommendations = [
  {
    text: "12 high-score leads match your Electrical Dealers ICP — review now",
    href: "/dashboard/leads",
  },
  {
    text: "IndiaMART response times are elevated — consider throttling that provider",
    href: "/dashboard/api-manager",
  },
  {
    text: "Panel Builders in Pune is trending — run a fresh search to capture new listings",
    href: "/dashboard/search",
  },
  {
    text: "34 leads have no email on file — try the Website Scanner to auto-fill contact details",
    href: "/dashboard/scanner",
  },
];

export function AiRecommendations() {
  return (
    <Card className="glass overflow-hidden">
      <CardHeader className="flex-row items-center gap-2 space-y-0">
        <div className="flex size-7 items-center justify-center rounded-lg bg-primary/15 text-primary">
          <Sparkles className="size-3.5" />
        </div>
        <CardTitle>AI Recommendations</CardTitle>
      </CardHeader>
      <div className="flex flex-col divide-y divide-border p-5 pt-3">
        {recommendations.map((rec) => (
          <Link
            key={rec.text}
            href={rec.href}
            className="group flex items-start gap-2 py-3 text-sm text-foreground/90 first:pt-0 last:pb-0 hover:text-foreground"
          >
            <span className="flex-1">{rec.text}</span>
            <ArrowUpRight className="mt-0.5 size-3.5 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5 group-hover:text-primary" />
          </Link>
        ))}
      </div>
    </Card>
  );
}
