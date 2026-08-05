import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { LeadSourceSelector, type LeadSource } from "@/components/search/lead-source-selector";

function renderSelector(value: LeadSource = "auto") {
  const onChange = vi.fn();
  render(<LeadSourceSelector value={value} onChange={onChange} />);
  return { onChange };
}

describe("LeadSourceSelector", () => {
  it("offers exactly the three sources", () => {
    renderSelector();

    const radios = screen.getAllByRole("radio");
    expect(radios).toHaveLength(3);
    expect(screen.getByLabelText(/Map — Public Data/)).toBeInTheDocument();
    expect(screen.getByLabelText(/API — Configured Providers/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Auto — API → Map fallback/)).toBeInTheDocument();
  });

  it("marks the current value as checked, and only that one", () => {
    renderSelector("map");

    expect(screen.getByLabelText(/Map — Public Data/)).toBeChecked();
    expect(screen.getByLabelText(/API — Configured Providers/)).not.toBeChecked();
    expect(screen.getByLabelText(/Auto/)).not.toBeChecked();
  });

  it("reports the chosen source", async () => {
    const user = userEvent.setup();
    const { onChange } = renderSelector("auto");

    await user.click(screen.getByLabelText(/Map — Public Data/));
    expect(onChange).toHaveBeenCalledWith("map");

    await user.click(screen.getByLabelText(/API — Configured Providers/));
    expect(onChange).toHaveBeenCalledWith("api");
  });

  it("says Map Mode needs no credentials, since that is the reason to pick it", () => {
    renderSelector();
    expect(screen.getByText(/No API key, no credentials/i)).toBeInTheDocument();
  });

  it("cannot be changed while a search is running", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<LeadSourceSelector value="auto" onChange={onChange} disabled />);

    await user.click(screen.getByLabelText(/Map — Public Data/));
    expect(onChange).not.toHaveBeenCalled();
  });
});
