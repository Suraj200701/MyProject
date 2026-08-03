import type { Metadata } from "next";
import { PageHeader } from "@/components/shared/page-header";
import { GoogleMapsSearch } from "@/components/google-maps/google-maps-search";

export const metadata: Metadata = {
  title: "Google Maps Search — LeadMaster AI",
  description:
    "Open a Google Maps search, extract with your own browser extension, then import the CSV — deduplicated, AI-scored and saved to your CRM.",
};

export default function GoogleMapsPage() {
  return (
    <div>
      <PageHeader
        title="Google Maps Search"
        description="Open a Maps search, export with your extractor extension, then import the CSV. Leads are deduplicated, scored and saved automatically."
      />
      <GoogleMapsSearch />
    </div>
  );
}
