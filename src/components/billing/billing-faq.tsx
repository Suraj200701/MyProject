import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const FAQ = [
  { q: "When am I billed?", a: "Your subscription renews monthly on the date you first subscribed. Credit top-ups are billed immediately." },
  { q: "What happens if I run out of credits?", a: "Searches pause until your next renewal, or you can buy a top-up pack at any time." },
  { q: "Can I change plans anytime?", a: "Yes — upgrades apply immediately with prorated billing; downgrades take effect at your next renewal." },
];

export function BillingFaq() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Billing FAQ</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {FAQ.map((item) => (
          <div key={item.q}>
            <p className="text-sm font-medium">{item.q}</p>
            <p className="mt-0.5 text-xs text-muted-foreground">{item.a}</p>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
