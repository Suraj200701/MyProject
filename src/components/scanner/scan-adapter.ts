import type { WebsiteScanOut } from "@/lib/api/types";
import type { RecentScan, ScanReport, ScanStageDef, SocialResult } from "@/components/scanner/types";

/**
 * Adapts `WebsiteScanOut` into the `ScanReport` shape the report view renders.
 *
 * Replaces `generateScanReport`, which produced every field from a hash of the
 * domain — a seeded PRNG invented the emails, phone numbers, GST number, social
 * handles and health metrics, so the same domain always "found" the same
 * fabricated details.
 *
 * Fields the backend genuinely cannot supply are left empty rather than filled:
 *
 *   * `contactPerson` — the backend explicitly returns null for this
 *     (identifying a named person needs a people-data source it doesn't have).
 *   * per-stage durations — the scan is one server-side operation that reports a
 *     single `scan_duration_ms`. Splitting that across six stages would be
 *     invented detail, so the breakdown carries the real total on the final
 *     stage and zero elsewhere.
 */

/** The stage list, kept as UI copy — it describes what the backend does. */
export const SCAN_STAGES: ScanStageDef[] = [
  { id: "connect", label: "Connecting to website", detail: "Validating URL & establishing secure handshake" },
  { id: "content", label: "Reading page content", detail: "Fetching the homepage and contact pages" },
  { id: "contacts", label: "Extracting contact details", detail: "Scanning for emails and phone numbers" },
  { id: "gst", label: "Detecting GST/business ID", detail: "Matching and checksum-verifying GSTIN" },
  { id: "social", label: "Scanning social links", detail: "Looking for linked social profiles" },
  { id: "confidence", label: "Calculating confidence score", detail: "Weighing signal quality across all findings" },
];

/** The four platforms the report grid always shows, in a fixed order. */
const SOCIAL_PLATFORMS: SocialResult["platform"][] = ["LinkedIn", "Facebook", "Instagram", "X"];

export function toScanReport(dto: WebsiteScanOut): ScanReport {
  const byPlatform = new Map((dto.social_links ?? []).map((s) => [s.platform, s]));

  return {
    id: dto.id,
    url: dto.url,
    domain: dto.domain,
    companyName: dto.company_name ?? "",
    // Always empty from the API — see the note above. The view renders it as
    // "Registered contact: —" rather than inventing a name.
    contactPerson: dto.contact_person ?? "—",
    confidence: dto.confidence_score,
    scanDurationMs: dto.scan_duration_ms,
    scannedAt: dto.created_at,
    contacts: {
      emails: dto.emails ?? [],
      phones: dto.phones ?? [],
    },
    gst: {
      number: dto.gst_number ?? "",
      // The backend only sets this for a checksum-valid GSTIN, so it means
      // "verified", not merely "shaped like one".
      verifiedFormat: dto.gst_verified,
    },
    social: SOCIAL_PLATFORMS.map((platform) => {
      const found = byPlatform.get(platform);
      return {
        platform,
        found: found?.found ?? false,
        handle: found?.handle ?? undefined,
      };
    }),
    health: {
      ssl: dto.ssl_valid,
      mobileFriendly: dto.mobile_friendly,
      loadTimeMs: dto.load_time_ms ?? 0,
      seoScore: dto.seo_score ?? 0,
    },
    // Real total on the last stage; the rest are 0 because the server does not
    // break the scan down per stage.
    stages: SCAN_STAGES.map((stage, index) => ({
      id: stage.id,
      label: stage.label,
      durationMs: index === SCAN_STAGES.length - 1 ? dto.scan_duration_ms : 0,
    })),
  };
}

export function toRecentScan(dto: WebsiteScanOut): RecentScan {
  return {
    id: dto.id,
    domain: dto.domain,
    confidence: dto.confidence_score,
    scannedAt: dto.created_at,
  };
}

/** Adds a scheme when the user typed a bare domain. */
export function normalizeUrl(raw: string): { url: string; domain: string } {
  const trimmed = raw.trim();
  const withScheme = /^https?:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`;
  try {
    const parsed = new URL(withScheme);
    return { url: withScheme, domain: parsed.hostname.replace(/^www\./, "") };
  } catch {
    // Let the backend's URL guard produce the authoritative error message.
    return { url: withScheme, domain: trimmed };
  }
}
