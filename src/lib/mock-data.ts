import type { ApiProvider, Lead, NotificationItem, SearchHistoryItem } from "./types";

const industries = [
  "Electrical Dealers",
  "Panel Builders",
  "Manufacturers",
  "OEM",
  "System Integrators",
  "EPC Companies",
  "Industrial Automation",
];

const cities = [
  { city: "Mumbai", country: "India" },
  { city: "Pune", country: "India" },
  { city: "Ahmedabad", country: "India" },
  { city: "Dubai", country: "UAE" },
  { city: "Singapore", country: "Singapore" },
  { city: "Austin", country: "United States" },
  { city: "Manchester", country: "United Kingdom" },
  { city: "Jakarta", country: "Indonesia" },
];

const companyTypes = ["Private Ltd", "LLP", "Partnership", "Public Ltd", "Proprietorship"];
const providers = ["Google Places", "Mappls", "IndiaMART", "TradeIndia", "JustDial", "LinkedIn"];
const statuses: Lead["status"][] = ["new", "contacted", "qualified", "converted", "lost"];

function seededRandom(seed: number) {
  let s = seed;
  return () => {
    s = (s * 9301 + 49297) % 233280;
    return s / 233280;
  };
}

function nameFromSeed(rand: () => number) {
  const first = ["Rohan", "Priya", "Amit", "Sara", "Vikram", "Neha", "Arjun", "Divya", "Karan", "Meera"];
  const last = ["Mehta", "Shah", "Kapoor", "Reddy", "Nair", "Iyer", "Verma", "Singh", "Gupta", "Rao"];
  return `${first[Math.floor(rand() * first.length)]} ${last[Math.floor(rand() * last.length)]}`;
}

const companyPrefixes = [
  "Apex",
  "Vertex",
  "Prime",
  "Nova",
  "Summit",
  "Bluewire",
  "Titan",
  "Orbit",
  "Meridian",
  "Ironclad",
  "Nexus",
  "Cascade",
];
const companySuffixes = [
  "Electricals",
  "Automation",
  "Controls",
  "Power Systems",
  "Switchgear",
  "Panels",
  "Engineering",
  "Industries",
  "Technologies",
  "Systems",
];

export function generateLeads(count: number): Lead[] {
  const rand = seededRandom(42);
  return Array.from({ length: count }, (_, i) => {
    const loc = cities[Math.floor(rand() * cities.length)];
    const industry = industries[Math.floor(rand() * industries.length)];
    const company = `${companyPrefixes[Math.floor(rand() * companyPrefixes.length)]} ${companySuffixes[Math.floor(rand() * companySuffixes.length)]}`;
    const score = Math.round(40 + rand() * 60);
    return {
      id: `lead_${i + 1}`,
      company,
      industry,
      city: loc.city,
      country: loc.country,
      contactName: nameFromSeed(rand),
      email: `contact${i + 1}@${company.toLowerCase().replace(/\s+/g, "")}.com`,
      phone: `+91 ${Math.floor(70000 + rand() * 9999)} ${Math.floor(10000 + rand() * 89999)}`,
      website: `www.${company.toLowerCase().replace(/\s+/g, "")}.com`,
      rating: Math.round((3 + rand() * 2) * 10) / 10,
      revenue: `$${(0.5 + rand() * 20).toFixed(1)}M`,
      leadScore: score,
      status: statuses[Math.floor(rand() * statuses.length)],
      companyType: companyTypes[Math.floor(rand() * companyTypes.length)],
      provider: providers[Math.floor(rand() * providers.length)],
      tags: [industry.split(" ")[0], score > 75 ? "High Value" : "Standard"],
      createdAt: new Date(Date.now() - Math.floor(rand() * 30) * 86400000).toISOString(),
      gst: rand() > 0.3 ? `27ABCDE${1000 + Math.floor(rand() * 8999)}F1Z5` : undefined,
      lat: 19.076 + (rand() - 0.5) * 8,
      lng: 72.877 + (rand() - 0.5) * 8,
      aiSummary: `${company} is a ${score > 75 ? "high-intent" : "moderate-intent"} ${industry.toLowerCase()} business based in ${loc.city}, showing strong signals in recent web activity and a growing digital footprint.`,
    };
  });
}

export const mockLeads = generateLeads(120);

export const apiProviders: ApiProvider[] = [
  { id: "google-places", name: "Google Places", category: "Maps", status: "healthy", usage: 8420, limit: 10000, latencyMs: 210, logo: "🗺️", description: "Business discovery & place details", connected: true },
  { id: "mappls", name: "Mappls (MapmyIndia)", category: "Maps", status: "healthy", usage: 3210, limit: 5000, latencyMs: 180, logo: "📍", description: "India-focused maps & POI search", connected: true },
  { id: "indiamart", name: "IndiaMART", category: "Business", status: "degraded", usage: 1890, limit: 2000, latencyMs: 640, logo: "🏭", description: "B2B supplier & manufacturer directory", connected: true },
  { id: "tradeindia", name: "TradeIndia", category: "Business", status: "healthy", usage: 990, limit: 2000, latencyMs: 300, logo: "🤝", description: "Trade leads and supplier network", connected: false },
  { id: "linkedin", name: "LinkedIn Sales Nav", category: "CRM", status: "healthy", usage: 540, limit: 1000, latencyMs: 410, logo: "💼", description: "Contact enrichment & company data", connected: true },
  { id: "openai", name: "OpenAI GPT", category: "AI", status: "healthy", usage: 15200, limit: 25000, latencyMs: 890, logo: "✨", description: "AI summaries & lead scoring", connected: true },
  { id: "hunter", name: "Hunter.io", category: "Business", status: "down", usage: 0, limit: 1000, latencyMs: 0, logo: "🎯", description: "Email discovery & verification", connected: false },
  { id: "justdial", name: "JustDial", category: "Search", status: "healthy", usage: 2740, limit: 5000, latencyMs: 250, logo: "🔍", description: "Local business search India", connected: true },
];

export const searchHistory: SearchHistoryItem[] = [
  { id: "s1", query: "Panel Builders in Pune", location: "Pune, India", results: 214, createdAt: "2026-07-29T08:12:00Z", status: "completed" },
  { id: "s2", query: "Electrical Dealers near Mumbai", location: "Mumbai, India", results: 178, createdAt: "2026-07-28T14:05:00Z", status: "completed" },
  { id: "s3", query: "Industrial Automation OEM", location: "Ahmedabad, India", results: 92, createdAt: "2026-07-28T09:40:00Z", status: "completed" },
  { id: "s4", query: "EPC Companies UAE", location: "Dubai, UAE", results: 0, createdAt: "2026-07-27T18:22:00Z", status: "failed" },
  { id: "s5", query: "System Integrators Singapore", location: "Singapore", results: 61, createdAt: "2026-07-27T11:00:00Z", status: "completed" },
];

export const notifications: NotificationItem[] = [
  { id: "n1", title: "Search completed", description: "214 new leads found for “Panel Builders in Pune”", type: "search", read: false, createdAt: "2026-07-29T08:12:00Z" },
  { id: "n2", title: "Export ready", description: "leads_export_july.xlsx is ready to download", type: "export", read: false, createdAt: "2026-07-29T07:50:00Z" },
  { id: "n3", title: "Provider degraded", description: "IndiaMART response times are elevated", type: "api", read: false, createdAt: "2026-07-29T06:30:00Z" },
  { id: "n4", title: "AI recommendation", description: "12 high-score leads match your Electrical Dealers ICP", type: "recommendation", read: true, createdAt: "2026-07-28T20:00:00Z" },
  { id: "n5", title: "Weekly report ready", description: "Your lead intelligence summary for this week is ready", type: "system", read: true, createdAt: "2026-07-27T09:00:00Z" },
];

export const leadGrowthData = [
  { month: "Feb", leads: 1240, converted: 180 },
  { month: "Mar", leads: 1890, converted: 260 },
  { month: "Apr", leads: 2210, converted: 340 },
  { month: "May", leads: 2640, converted: 410 },
  { month: "Jun", leads: 3120, converted: 520 },
  { month: "Jul", leads: 3980, converted: 640 },
];

export const industryDistribution = [
  { name: "Electrical Dealers", value: 32 },
  { name: "Panel Builders", value: 24 },
  { name: "Manufacturers", value: 18 },
  { name: "System Integrators", value: 12 },
  { name: "EPC Companies", value: 9 },
  { name: "Industrial Automation", value: 5 },
];

export const countryAnalytics = [
  { country: "India", leads: 4820 },
  { country: "UAE", leads: 980 },
  { country: "Singapore", leads: 610 },
  { country: "United States", leads: 540 },
  { country: "United Kingdom", leads: 320 },
  { country: "Indonesia", leads: 280 },
];

export const searchAnalytics = [
  { day: "Mon", searches: 42 },
  { day: "Tue", searches: 58 },
  { day: "Wed", searches: 51 },
  { day: "Thu", searches: 67 },
  { day: "Fri", searches: 74 },
  { day: "Sat", searches: 33 },
  { day: "Sun", searches: 21 },
];

export const apiUsageData = apiProviders.map((p) => ({ name: p.name, usage: p.usage, limit: p.limit }));

export const exportAnalytics = [
  { month: "Feb", csv: 12, excel: 8, pdf: 3 },
  { month: "Mar", csv: 18, excel: 11, pdf: 5 },
  { month: "Apr", csv: 22, excel: 14, pdf: 6 },
  { month: "May", csv: 19, excel: 17, pdf: 8 },
  { month: "Jun", csv: 27, excel: 20, pdf: 9 },
  { month: "Jul", csv: 34, excel: 24, pdf: 12 },
];

export const dashboardStats = {
  totalLeads: 8420,
  todayLeads: 214,
  conversionRate: 16.4,
  avgLeadScore: 72,
  searchCount: 341,
  creditsRemaining: 6840,
  creditsTotal: 10000,
};
