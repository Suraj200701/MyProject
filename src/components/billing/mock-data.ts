export interface Invoice {
  id: string;
  number: string;
  date: string;
  amount: string;
  status: "Paid" | "Pending" | "Failed";
}

export const INVOICES: Invoice[] = [
  { id: "inv-1", number: "INV-2026-0712", date: "2026-07-01", amount: "$249.00", status: "Paid" },
  { id: "inv-2", number: "INV-2026-0611", date: "2026-06-01", amount: "$249.00", status: "Paid" },
  { id: "inv-3", number: "INV-2026-0509", date: "2026-05-01", amount: "$249.00", status: "Paid" },
  { id: "inv-4", number: "INV-2026-0408", date: "2026-04-01", amount: "$249.00", status: "Paid" },
  { id: "inv-5", number: "INV-2026-0307", date: "2026-03-01", amount: "$199.00", status: "Paid" },
  { id: "inv-6", number: "INV-2026-0206", date: "2026-02-01", amount: "$199.00", status: "Failed" },
];

export interface Plan {
  id: string;
  name: string;
  price: string;
  period: string;
  features: string[];
  highlight?: boolean;
}

export const PLANS: Plan[] = [
  { id: "free", name: "Free", price: "$0", period: "/mo", features: ["100 credits/mo", "1 seat", "Basic search"] },
  { id: "pro", name: "Pro", price: "$249", period: "/mo", features: ["10,000 credits/mo", "5 seats", "AI lead scoring", "Website scanner"], highlight: true },
  { id: "business", name: "Business", price: "$699", period: "/mo", features: ["50,000 credits/mo", "20 seats", "API Manager", "Priority support"] },
  { id: "enterprise", name: "Enterprise", price: "Custom", period: "", features: ["Unlimited credits", "Unlimited seats", "SSO & SLA", "Dedicated CSM"] },
];

export const CREDIT_PACKS = [
  { id: "c1", label: "1,000 credits", price: "$29" },
  { id: "c2", label: "5,000 credits", price: "$119" },
  { id: "c3", label: "20,000 credits", price: "$399" },
];
