import type { ScanReport, ScanStageDef, RecentScan, SocialResult } from "./types";

export const SCAN_STAGES: ScanStageDef[] = [
  { id: "connect", label: "Connecting to website", detail: "Resolving domain & establishing secure handshake" },
  { id: "content", label: "Reading page content", detail: "Parsing DOM, metadata and page structure" },
  { id: "contacts", label: "Extracting contact details", detail: "Scanning for emails, phone numbers & addresses" },
  { id: "gst", label: "Detecting GST/business ID", detail: "Matching registration number patterns" },
  { id: "social", label: "Scanning social links", detail: "Looking for verified social profiles" },
  { id: "confidence", label: "Calculating confidence score", detail: "Weighing signal quality across all findings" },
];

export const EXAMPLE_URLS = [
  "https://acmesupplies.com",
  "https://brightpath-consulting.io",
  "https://nova-retailgroup.com",
  "https://summitlogistics.co.in",
];

export const INITIAL_RECENT_SCANS: RecentScan[] = [
  { id: "rs-1", domain: "zenithtechworks.com", confidence: 92, scannedAt: "2026-07-27T09:14:00.000Z" },
  { id: "rs-2", domain: "harborline-freight.com", confidence: 76, scannedAt: "2026-07-26T15:42:00.000Z" },
  { id: "rs-3", domain: "pinegrove-realty.in", confidence: 64, scannedAt: "2026-07-24T11:05:00.000Z" },
  { id: "rs-4", domain: "quantumedge-labs.co", confidence: 88, scannedAt: "2026-07-21T08:30:00.000Z" },
];

/** Deterministic string hash -> seeded PRNG (mulberry32) so the same domain always yields the same "findings". */
function hashString(input: string): number {
  let h = 1779033703 ^ input.length;
  for (let i = 0; i < input.length; i++) {
    h = Math.imul(h ^ input.charCodeAt(i), 3432918353);
    h = (h << 13) | (h >>> 19);
  }
  return h >>> 0;
}

function mulberry32(seed: number) {
  let a = seed;
  return function random() {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function normalizeUrl(raw: string): { url: string; domain: string } {
  let value = raw.trim();
  if (!value) return { url: "", domain: "" };
  if (!/^https?:\/\//i.test(value)) value = `https://${value}`;
  let domain = value;
  try {
    domain = new URL(value).hostname.replace(/^www\./, "");
  } catch {
    domain = value.replace(/^https?:\/\//i, "").replace(/^www\./, "").split("/")[0];
  }
  return { url: value, domain };
}

const FIRST_NAMES = ["Aarav", "Priya", "Rohan", "Meera", "Kabir", "Anjali", "Vikram", "Divya"];
const LAST_NAMES = ["Sharma", "Mehta", "Iyer", "Kapoor", "Nair", "Chawla", "Reddy", "Bose"];
const STATE_CODES = ["07", "27", "29", "33", "36", "19", "24", "09"];

function slugCompanyName(domain: string): string {
  const base = domain.split(".")[0] ?? domain;
  return base
    .split(/[-_]/)
    .filter(Boolean)
    .map((part) => part[0]?.toUpperCase() + part.slice(1))
    .join(" ");
}

export function generateScanReport(rawUrl: string, scanDurationMs: number, stageDurations: Record<string, number>): ScanReport {
  const { url, domain } = normalizeUrl(rawUrl);
  const rand = mulberry32(hashString(domain || url));

  const companySlug = (domain.split(".")[0] || "contact").toLowerCase();

  const emailCount = 1 + Math.floor(rand() * 2);
  const emails = Array.from({ length: emailCount }, (_, i) =>
    i === 0 ? `info@${domain}` : `sales@${domain}`,
  );

  const phoneCount = 1 + Math.floor(rand() * 2);
  const phones = Array.from({ length: phoneCount }, () => {
    const n = Math.floor(rand() * 900000000 + 100000000);
    return `+91 ${String(n).slice(0, 5)} ${String(n).slice(5)}`;
  });

  const stateCode = STATE_CODES[Math.floor(rand() * STATE_CODES.length)];
  const panLetters = Array.from({ length: 5 }, () => String.fromCharCode(65 + Math.floor(rand() * 26))).join("");
  const panDigits = Array.from({ length: 4 }, () => Math.floor(rand() * 10)).join("");
  const panCheck = String.fromCharCode(65 + Math.floor(rand() * 26));
  const gstNumber = `${stateCode}${panLetters}${panDigits}${panCheck}1Z${Math.floor(rand() * 10)}`;
  const gstFound = rand() > 0.15;

  const platforms: SocialResult["platform"][] = ["LinkedIn", "Facebook", "Instagram", "X"];
  const social: SocialResult[] = platforms.map((platform) => {
    const found = rand() > 0.35;
    return {
      platform,
      found,
      handle: found ? `@${companySlug}` : undefined,
    };
  });

  const ssl = rand() > 0.08;
  const mobileFriendly = rand() > 0.2;
  const loadTimeMs = Math.round(600 + rand() * 2200);
  const seoScore = Math.round(55 + rand() * 40);

  const signals = [gstFound, ssl, mobileFriendly, ...social.map((s) => s.found)];
  const positiveSignals = signals.filter(Boolean).length;
  const confidence = Math.min(98, Math.max(38, Math.round((positiveSignals / signals.length) * 78 + 18 + rand() * 6)));

  const contactPerson = `${FIRST_NAMES[Math.floor(rand() * FIRST_NAMES.length)]} ${LAST_NAMES[Math.floor(rand() * LAST_NAMES.length)]}`;
  const companyName = slugCompanyName(domain || companySlug);

  return {
    id: `scan-${Date.now()}`,
    url,
    domain: domain || url,
    companyName,
    contactPerson,
    confidence,
    scanDurationMs,
    scannedAt: new Date().toISOString(),
    contacts: {
      emails,
      phones,
    },
    gst: {
      number: gstFound ? gstNumber : "Not detected",
      verifiedFormat: gstFound,
    },
    social,
    health: { ssl, mobileFriendly, loadTimeMs, seoScore },
    stages: SCAN_STAGES.map((s) => ({ id: s.id, label: s.label, durationMs: stageDurations[s.id] ?? 0 })),
  };
}
