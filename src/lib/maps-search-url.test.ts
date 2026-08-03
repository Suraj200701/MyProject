import { describe, expect, it } from "vitest";
import { buildMapsSearchUrl, GOOGLE_MAPS_SEARCH_BASE } from "./maps-search-url";

describe("buildMapsSearchUrl", () => {
  it("builds the documented /maps/search/ form with + between terms", () => {
    expect(buildMapsSearchUrl("dentists", "Ahmedabad")).toBe(
      "https://www.google.com/maps/search/dentists+Ahmedabad",
    );
  });

  it("works without a location", () => {
    expect(buildMapsSearchUrl("dentists")).toBe("https://www.google.com/maps/search/dentists");
  });

  it("joins multi-word keywords and locations with +", () => {
    expect(buildMapsSearchUrl("dental clinics", "New Delhi")).toBe(
      "https://www.google.com/maps/search/dental+clinics+New+Delhi",
    );
  });

  it("trims surrounding whitespace", () => {
    expect(buildMapsSearchUrl("  cafes  ", "  Pune  ")).toBe(
      "https://www.google.com/maps/search/cafes+Pune",
    );
  });

  /**
   * The keyword goes straight into a URL path, so anything that could terminate
   * the path or start a query string has to be percent-encoded.
   */
  it("escapes characters that would break out of the path", () => {
    const url = buildMapsSearchUrl("bars & grills?x=1#frag", "Goa");
    expect(url?.startsWith(GOOGLE_MAPS_SEARCH_BASE)).toBe(true);
    const path = url!.slice(GOOGLE_MAPS_SEARCH_BASE.length);
    expect(path).not.toContain("&");
    expect(path).not.toContain("?");
    expect(path).not.toContain("#");
    expect(path).not.toContain("/");
  });

  it("returns null for an empty or whitespace-only keyword", () => {
    // Null rather than a bare base URL: opening /maps/search/ with no query is
    // a worse outcome than the button staying disabled.
    expect(buildMapsSearchUrl("")).toBeNull();
    expect(buildMapsSearchUrl("   ")).toBeNull();
    expect(buildMapsSearchUrl("   ", "Ahmedabad")).toBeNull();
  });

  it("matches the backend's builder for the same input", () => {
    // backend/services/import_service.py uses quote_plus, which produces this.
    expect(buildMapsSearchUrl("restaurants", "Ahmedabad")).toBe(
      "https://www.google.com/maps/search/restaurants+Ahmedabad",
    );
  });
});
