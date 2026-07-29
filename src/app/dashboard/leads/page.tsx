import { PageHeader } from "@/components/shared/page-header";
import { LeadsDataTable } from "@/components/leads/data-table";
import { mockLeads } from "@/lib/mock-data";

export default function LeadsPage() {
  return (
    <div>
      <PageHeader
        title="Lead Database"
        description="Browse, filter, and manage every lead discovered across your searches."
      />
      <LeadsDataTable data={mockLeads} />
    </div>
  );
}
