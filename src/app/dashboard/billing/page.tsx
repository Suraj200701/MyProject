import { PageHeader } from "@/components/shared/page-header";
import { PaymentMethodDialog } from "@/components/billing/payment-method-dialog";
import { CurrentPlanCard } from "@/components/billing/current-plan-card";
import { UsageRow } from "@/components/billing/usage-row";
import { CreditsAddons } from "@/components/billing/credits-addons";
import { InvoiceHistory } from "@/components/billing/invoice-history";
import { BillingFaq } from "@/components/billing/billing-faq";

export default function BillingPage() {
  return (
    <div>
      <PageHeader
        title="Billing"
        description="Manage your subscription, usage, and payment details."
        actions={<PaymentMethodDialog />}
      />

      <div className="space-y-5">
        <UsageRow />

        <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
          <div className="lg:col-span-2 space-y-5">
            <CurrentPlanCard />
            <InvoiceHistory />
          </div>
          <div className="space-y-5">
            <CreditsAddons />
            <BillingFaq />
          </div>
        </div>
      </div>
    </div>
  );
}
