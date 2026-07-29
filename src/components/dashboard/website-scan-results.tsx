import { ScanLine } from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";

interface ScanResult {
  id: string;
  company: string;
  website: string;
  confidence: number;
  fields: string[];
}

const scanResults: ScanResult[] = [
  {
    id: "scan_1",
    company: "Apex Switchgear",
    website: "www.apexswitchgear.com",
    confidence: 94,
    fields: ["GST Found", "Email Found", "Phone Found"],
  },
  {
    id: "scan_2",
    company: "Nova Power Systems",
    website: "www.novapowersystems.com",
    confidence: 81,
    fields: ["Email Found", "Address Found"],
  },
  {
    id: "scan_3",
    company: "Titan Panels",
    website: "www.titanpanels.com",
    confidence: 62,
    fields: ["Phone Found"],
  },
  {
    id: "scan_4",
    company: "Meridian Automation",
    website: "www.meridianautomation.com",
    confidence: 88,
    fields: ["GST Found", "Email Found"],
  },
];

export function WebsiteScanResults() {
  return (
    <Card className="glass overflow-hidden">
      <CardHeader className="flex-row items-center gap-2 space-y-0">
        <div className="flex size-7 items-center justify-center rounded-lg bg-accent/15 text-accent">
          <ScanLine className="size-3.5" />
        </div>
        <CardTitle>Website Scan Results</CardTitle>
      </CardHeader>
      <div className="flex flex-col divide-y divide-border p-5 pt-3">
        {scanResults.map((scan) => (
          <div key={scan.id} className="flex flex-col gap-2 py-3 first:pt-0 last:pb-0">
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-foreground/90">{scan.company}</p>
                <p className="truncate text-xs text-muted-foreground">{scan.website}</p>
              </div>
              <span className="shrink-0 text-xs font-medium tabular-nums text-muted-foreground">
                {scan.confidence}%
              </span>
            </div>
            <Progress value={scan.confidence} />
            <div className="flex flex-wrap gap-1.5">
              {scan.fields.map((field) => (
                <Badge key={field} variant="success" className="text-[11px]">
                  {field}
                </Badge>
              ))}
            </div>
          </div>
        ))}
      </div>
      <div className="border-t border-border px-5 py-3">
        <Link href="/dashboard/scanner" className="text-xs font-medium text-primary hover:underline">
          Scan another website
        </Link>
      </div>
    </Card>
  );
}
