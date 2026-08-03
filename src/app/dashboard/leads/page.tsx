import { PageHeader } from "@/components/shared/page-header";
import { LeadsDataTable } from "@/components/leads/data-table";

export default function LeadsPage() {
  return (
    <div>
      <PageHeader
        title="Lead Database"
        description="Browse, filter, and manage every lead discovered across your searches."
      />
      {/* The table fetches its own page from GET /leads — paging, sorting and
          filtering all happen server-side. */}
      <LeadsDataTable />
    </div>
  );
}
