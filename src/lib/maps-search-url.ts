/**
 * Builds the Google Maps search URL for a keyword + location.
 *
 * Mirrors `backend/services/import_service.build_maps_search_url` so the link
 * can be shown and opened without a round-trip. The backend keeps its own copy
 * because it stores the query on the import history row — one of the two has to
 * be authoritative for what was recorded, and it is the server.
 *
 * `encodeURIComponent` then `%20` -> `+`: Maps' documented `/maps/search/` path
 * treats `+` as the term separator, and `encodeURIComponent` alone would emit
 * `%20`, which works but does not match the canonical form.
 */
export const GOOGLE_MAPS_SEARCH_BASE = "https://www.google.com/maps/search/";

export function buildMapsSearchUrl(keyword: string, location?: string): string | null {
  const trimmedKeyword = keyword.trim();
  if (!trimmedKeyword) return null;

  const trimmedLocation = (location ?? "").trim();
  const query = trimmedLocation ? `${trimmedKeyword} ${trimmedLocation}` : trimmedKeyword;

  return GOOGLE_MAPS_SEARCH_BASE + encodeURIComponent(query).replace(/%20/g, "+");
}
