"use client";

import { toast } from "sonner";
import { Download } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { AsyncContent } from "@/components/shared/async-content";
import { useInvoices } from "@/lib/api/queries";
import { formatDate, formatMoney } from "@/components/billing/format";
import type { InvoiceOut } from "@/lib/api/types";

const STATUS_VARIANT: Record<InvoiceOut["status"], "success" | "warning" | "danger"> = {
  paid: "success",
  pending: "warning",
  failed: "danger",
};

const STATUS_LABEL: Record<InvoiceOut["status"], string> = {
  paid: "Paid",
  pending: "Pending",
  failed: "Failed",
};

export function InvoiceHistory() {
  const { data, isPending, isError, error } = useInvoices({ page_size: 20 });
  const invoices = data?.items ?? [];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Invoice History</CardTitle>
      </CardHeader>
      <AsyncContent
        isPending={isPending}
        isError={isError}
        error={error}
        isEmpty={invoices.length === 0}
        emptyMessage="No invoices yet."
        className="min-h-[140px] p-5"
      >
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-muted-foreground">
                  <th className="py-2 pr-3 font-medium">Invoice</th>
                  <th className="py-2 pr-3 font-medium">Date</th>
                  <th className="py-2 pr-3 font-medium">Amount</th>
                  <th className="py-2 pr-3 font-medium">Status</th>
                  <th className="py-2 pl-3 text-right font-medium">
                    <span className="sr-only">Download</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {invoices.map((invoice) => (
                  <tr key={invoice.id} className="border-b border-border/60 last:border-0">
                    <td className="py-2.5 pr-3 font-medium text-foreground">{invoice.invoice_number}</td>
                    <td className="py-2.5 pr-3 text-muted-foreground">{formatDate(invoice.created_at)}</td>
                    <td className="py-2.5 pr-3 tabular-nums text-foreground">
                      {formatMoney(invoice.amount_cents, invoice.currency)}
                    </td>
                    <td className="py-2.5 pr-3">
                      <Badge variant={STATUS_VARIANT[invoice.status]}>
                        {STATUS_LABEL[invoice.status]}
                      </Badge>
                    </td>
                    <td className="py-2.5 pl-3 text-right">
                      {/* The PDF is hosted by Stripe. Without a URL there is
                          nothing to download, so the button is disabled rather
                          than claiming a download that cannot happen. */}
                      <Button
                        variant="ghost"
                        size="icon"
                        disabled={!invoice.invoice_pdf_url}
                        title={invoice.invoice_pdf_url ? "Download invoice" : "No PDF available"}
                        onClick={() => {
                          if (!invoice.invoice_pdf_url) return;
                          window.open(invoice.invoice_pdf_url, "_blank", "noopener,noreferrer");
                          toast.success(`Opening ${invoice.invoice_number}`);
                        }}
                      >
                        <Download className="size-3.5" />
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </AsyncContent>
    </Card>
  );
}
