import { fireEvent, render, screen } from "@testing-library/react";
import type { Plan, Stop } from "../types";
import { TourPoster } from "./TourPoster";

const stop = (metro: string, date: string, extra: Partial<Stop> = {}): Stop => ({
  date, metro, lat: 0, lon: 0, drive_km: 100, travel_day_before: false, label: "unserved", demand: 80, reach: 0, gap: 80,
  venue: { id: "v", name: "Rumba Café" }, backup_venues: [], openers: [{ id: "o", name: "Snarls", badge: "based_here" }],
  sponsors: [], promo: [], why: "", ...extra,
});

const plan: Plan = {
  artist: "Easy Wanderlings", on_qloo: false, signal_names: ["Prateek Kuhad", "Fleet Foxes"], headline: "", summary: "Six dates.",
  sponsor_strategy: "", risks: [], days_off: ["2027-03-10"], dropped: [], total_km: 3888, composed_by: "llm", outreach: {},
  stops: [stop("Columbus, OH", "2027-04-02"), stop("Chicago, IL", "2027-04-03", { label: "proven", venue: null, openers: [], travel_day_before: true })],
};

describe("TourPoster", () => {
  it("renders the date list, says whose fans were mapped, and selects a date", () => {
    const onSelect = vi.fn();
    render(<TourPoster plan={plan} active={0} onSelect={onSelect} />);
    expect(screen.getByText("Tour plan, mapped from fans of Prateek Kuhad, Fleet Foxes")).toBeTruthy();
    expect(screen.getByText("Rumba Café with Snarls")).toBeTruthy();
    expect(screen.getByText("Venue to find")).toBeTruthy();
    expect(screen.getByText("travel day before")).toBeTruthy();
    expect(screen.getByText(/2 shows, 3,888 km on the road, 1 day off/)).toBeTruthy();
    fireEvent.click(screen.getByText("Chicago"));
    expect(onSelect).toHaveBeenCalledWith(1);
  });
});
