import type { ApiProvider } from "@/lib/types";

/**
 * Local, presentation-only mock data helpers for the API Manager page.
 * Nothing here is persisted or wired to a real backend — it exists purely
 * to make the console feel alive (sparklines, uptime, canned responses).
 */

function hashString(input: string): number {
  let h = 0;
  for (let i = 0; i < input.length; i++) {
    h = (h * 31 + input.charCodeAt(i)) | 0;
  }
  return Math.abs(h);
}

function seededRandom(seed: number) {
  let s = seed % 2147483647;
  if (s <= 0) s += 2147483646;
  return () => {
    s = (s * 16807) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

function randomFor(providerId: string, salt = 0) {
  return seededRandom(hashString(providerId) + salt * 7919);
}

export const DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export interface SparklineDay {
  day: string;
  value: number;
}

/** 7 fake days of usage volume, shaped loosely around the provider's current usage. */
export function getSparklineData(provider: ApiProvider): SparklineDay[] {
  const rand = randomFor(provider.id, 1);
  const base = Math.max(provider.usage, 40);
  return DAY_LABELS.map((day) => {
    const jitter = 0.55 + rand() * 0.7; // 0.55x - 1.25x
    return { day, value: Math.max(4, Math.round((base / 7) * jitter)) };
  });
}

/** Invented uptime percentage, biased by current health status. */
export function getUptimePercent(provider: ApiProvider): number {
  const rand = randomFor(provider.id, 2);
  switch (provider.status) {
    case "healthy":
      return Math.round((99.4 + rand() * 0.58) * 100) / 100;
    case "degraded":
      return Math.round((95 + rand() * 3.4) * 100) / 100;
    case "down":
    default:
      return Math.round((80 + rand() * 11) * 100) / 100;
  }
}

export type Trend = "up" | "down" | "flat";

/** Invented 24h trend direction, biased by current health status. */
export function getTrend(provider: ApiProvider): Trend {
  const rand = randomFor(provider.id, 3);
  const r = rand();
  if (provider.status === "down") return r < 0.7 ? "down" : "flat";
  if (provider.status === "degraded") return r < 0.5 ? "down" : r < 0.8 ? "flat" : "up";
  return r < 0.55 ? "up" : r < 0.85 ? "flat" : "down";
}

/** Deterministic-looking masked API key. Bump `version` to simulate "regenerating" it. */
export function getMaskedApiKey(providerId: string, version = 0): string {
  const rand = randomFor(providerId, 100 + version);
  const chars = "abcdef0123456789";
  let tail = "";
  for (let i = 0; i < 4; i++) tail += chars[Math.floor(rand() * chars.length)];
  const prefix = providerId.slice(0, 3);
  return `sk_live_${prefix}_••••••••••••${tail}`;
}

export interface MockApiResponse {
  httpStatus: number;
  latencyMs: number;
  body: Record<string, unknown>;
}

/** Plausible, category-flavored JSON payload for the "Test Connection" preview. */
export function getMockResponse(provider: ApiProvider): MockApiResponse {
  const rand = randomFor(provider.id, 4);
  const latencyMs = Math.max(60, Math.round(provider.latencyMs * (0.85 + rand() * 0.3)));

  let body: Record<string, unknown>;

  switch (provider.category) {
    case "Search":
      body = {
        status: "OK",
        query: "electrical panel builders in Pune",
        result_count: 214,
        results: [
          { name: "Apex Switchgear Co.", rating: 4.3, address: "MG Road, Pune", phone: "+91 98765 43210" },
          { name: "Vertex Controls Pvt Ltd", rating: 4.6, address: "Hinjewadi, Pune", phone: "+91 91234 56789" },
        ],
      };
      break;
    case "Maps":
      body = {
        status: "OK",
        results: [
          {
            formatted_address: "Bandra Kurla Complex, Mumbai, Maharashtra 400051, India",
            geometry: { location: { lat: 19.0662, lng: 72.8697 } },
            place_id: "ChIJ2xU3f8u_wjsR5tzP1sQfX9c",
            types: ["point_of_interest", "establishment"],
          },
        ],
      };
      break;
    case "Business":
      body = {
        status: "OK",
        total: provider.usage || 1890,
        companies: [
          { name: "Nova Power Systems", industry: "Panel Builders", city: "Ahmedabad", verified: true },
          { name: "Titan Industries", industry: "Manufacturers", city: "Mumbai", verified: false },
        ],
      };
      break;
    case "CRM":
      body = {
        status: "OK",
        contact: {
          name: "Rohan Mehta",
          title: "VP of Procurement",
          company: "Meridian Automation",
          email: "rohan.mehta@meridianauto.com",
          connections: 512,
        },
      };
      break;
    case "AI":
    default:
      body = {
        id: "cmpl-8f9a2b3c",
        model: "gpt-4o-mini",
        choices: [
          {
            text: "This lead shows strong purchase intent based on recent RFQ activity and a 40% increase in website engagement.",
            finish_reason: "stop",
          },
        ],
        usage: { prompt_tokens: 128, completion_tokens: 42, total_tokens: 170 },
      };
      break;
  }

  return { httpStatus: 200, latencyMs, body };
}

export const CATEGORY_TABS = ["All", "Search", "Maps", "Business", "CRM", "AI"] as const;
export type CategoryTab = (typeof CATEGORY_TABS)[number];

export function categoryTabLabel(tab: CategoryTab): string {
  return tab === "All" ? "All" : `${tab} APIs`;
}
