import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { MapResult } from "@/lib/api/types";

/**
 * The real `MapView` boots Leaflet, which needs real layout — jsdom reports
 * every element as 0×0 and Leaflet throws. The map is verified in a browser
 * instead; here it is replaced by a marker count so the flow can be tested.
 */
vi.mock("@/components/search/map-view", () => ({
  MapView: ({ results }: { results: MapResult[] }) => (
    <div data-testid="map">{results.length} markers</div>
  ),
}));

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

const toastError = vi.fn();
const toastInfo = vi.fn();
const toastSuccess = vi.fn();
vi.mock("sonner", () => ({
  toast: { error: toastError, info: toastInfo, success: toastSuccess },
}));

const extractMutate = vi.fn();
const importMutate = vi.fn();
let extractPending = false;
let importPending = false;

vi.mock("@/lib/api/queries", () => ({
  useExtractMapResults: () => ({ mutate: extractMutate, isPending: extractPending }),
  useImportMapResults: () => ({ mutate: importMutate, isPending: importPending }),
}));

const { MapMode } = await import("@/components/search/map-mode");

function result(over: Partial<MapResult> = {}): MapResult {
  return {
    id: "r0",
    company_name: "Sunrise Diagnostics",
    category: "hospital",
    address: "12 Link Road",
    city: "Bhopal",
    country: "India",
    phone: "+91 755 400 1001",
    email: null,
    website: "https://sunrise.example.com",
    latitude: 23.2599,
    longitude: 77.4126,
    rating: null,
    source_provider: "Overpass API",
    osm_url: "https://www.openstreetmap.org/node/1001",
    ...over,
  };
}

/** Types a keyword and location, then presses Open Map. */
async function extract(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText("Keyword"), "hospital");
  await user.type(screen.getByLabelText("Location"), "Bhopal");
  await user.click(screen.getByRole("button", { name: /Open Map/i }));
}

beforeEach(() => {
  vi.clearAllMocks();
  extractPending = false;
  importPending = false;
});

describe("MapMode", () => {
  it("will not extract until both a keyword and a location are given", async () => {
    const user = userEvent.setup();
    render(<MapMode />);

    const button = screen.getByRole("button", { name: /Open Map/i });
    expect(button).toBeDisabled();

    await user.type(screen.getByLabelText("Keyword"), "hospital");
    expect(button).toBeDisabled();

    await user.type(screen.getByLabelText("Location"), "Bhopal");
    expect(button).toBeEnabled();
  });

  it("sends the keyword and location, and shows what came back", async () => {
    const user = userEvent.setup();
    extractMutate.mockImplementation((_body, opts) =>
      opts.onSuccess({ results: [result(), result({ id: "r1", company_name: "Cedar Clinic" })], provider_runs: [], blocked_reason: null }),
    );
    render(<MapMode />);
    await extract(user);

    expect(extractMutate).toHaveBeenCalledWith(
      { query: "hospital", location: "Bhopal" },
      expect.anything(),
    );
    expect(await screen.findByText(/Found/)).toBeInTheDocument();
    expect(screen.getByText("Sunrise Diagnostics")).toBeInTheDocument();
    expect(screen.getByText("Cedar Clinic")).toBeInTheDocument();
    expect(screen.getByTestId("map")).toHaveTextContent("2 markers");
  });

  it("pre-selects every result so Import is immediately usable", async () => {
    const user = userEvent.setup();
    extractMutate.mockImplementation((_b, opts) =>
      opts.onSuccess({ results: [result(), result({ id: "r1" })], provider_runs: [], blocked_reason: null }),
    );
    render(<MapMode />);
    await extract(user);

    expect(await screen.findByRole("button", { name: /Import 2 selected leads/i })).toBeEnabled();
  });

  it("imports only the rows still ticked", async () => {
    const user = userEvent.setup();
    extractMutate.mockImplementation((_b, opts) =>
      opts.onSuccess({
        results: [result(), result({ id: "r1", company_name: "Cedar Clinic" })],
        provider_runs: [],
        blocked_reason: null,
      }),
    );
    importMutate.mockImplementation((_rows, opts) =>
      opts.onSuccess({ imported: 1, duplicates: 0, lead_ids: ["lead-1"] }),
    );
    render(<MapMode />);
    await extract(user);

    await user.click(await screen.findByLabelText("Select Cedar Clinic"));
    await user.click(screen.getByRole("button", { name: /Import 1 selected lead/i }));

    const [rows] = importMutate.mock.calls[0];
    expect(rows).toHaveLength(1);
    expect(rows[0].company_name).toBe("Sunrise Diagnostics");
  });

  it("reports duplicates rather than pretending everything was new", async () => {
    const user = userEvent.setup();
    extractMutate.mockImplementation((_b, opts) =>
      opts.onSuccess({ results: [result()], provider_runs: [], blocked_reason: null }),
    );
    importMutate.mockImplementation((_rows, opts) =>
      opts.onSuccess({ imported: 0, duplicates: 1, lead_ids: [] }),
    );
    render(<MapMode />);
    await extract(user);
    await user.click(await screen.findByRole("button", { name: /Import 1 selected lead/i }));

    await waitFor(() => expect(toastSuccess).toHaveBeenCalled());
    expect(toastSuccess.mock.calls[0][0]).toMatch(/1 already in your database/);
  });

  it("distinguishes a blocked provider from an empty area, and offers a retry", async () => {
    const user = userEvent.setup();
    extractMutate.mockImplementation((_b, opts) =>
      opts.onSuccess({ results: [], provider_runs: [], blocked_reason: "Overpass returned 429" }),
    );
    render(<MapMode />);
    await extract(user);

    expect(await screen.findByText(/didn't answer/i)).toBeInTheDocument();
    expect(screen.getByText(/429/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Retry/i })).toBeInTheDocument();
    // Not the "no results" empty state — that would misdescribe the cause.
    expect(screen.queryByText(/No public results found/i)).not.toBeInTheDocument();
  });

  it("says plainly when the area genuinely has nothing", async () => {
    const user = userEvent.setup();
    extractMutate.mockImplementation((_b, opts) =>
      opts.onSuccess({ results: [], provider_runs: [], blocked_reason: null }),
    );
    render(<MapMode />);
    await extract(user);

    expect(await screen.findByText(/No public results found/i)).toBeInTheDocument();
    expect(toastInfo).toHaveBeenCalled();
  });

  it("surfaces an extraction failure instead of a fake empty state", async () => {
    const user = userEvent.setup();
    extractMutate.mockImplementation((_b, opts) => opts.onError(new Error("network down")));
    render(<MapMode />);
    await extract(user);

    await waitFor(() => expect(toastError).toHaveBeenCalled());
    expect(screen.queryByText(/Found/)).not.toBeInTheDocument();
  });

  it("credits OpenStreetMap, which the ODbL licence requires", async () => {
    const user = userEvent.setup();
    extractMutate.mockImplementation((_b, opts) =>
      opts.onSuccess({ results: [result()], provider_runs: [], blocked_reason: null }),
    );
    render(<MapMode />);
    await extract(user);

    const credit = await screen.findByRole("link", { name: /OpenStreetMap/i });
    expect(credit).toHaveAttribute("href", "https://www.openstreetmap.org/copyright");
    expect(screen.getByText(/ODbL/)).toBeInTheDocument();
  });

  it("shows a busy state while extracting", async () => {
    extractPending = true;
    render(<MapMode />);

    expect(screen.getByRole("button", { name: /Extracting/i })).toBeDisabled();
  });
});
