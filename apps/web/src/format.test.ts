import { city, km, shortDate, stepTitle } from "./format";

describe("format", () => {
  it("speaks the musician's language, not node names", () => {
    expect(stepTitle("fanout")).toBe("Found venues, openers, sponsors and promo spots");
    expect(stepTitle("unknown_node")).toBe("unknown_node");
  });
  it("splits metro labels and formats dates and distances", () => {
    expect(city("Columbus, OH")).toEqual({ name: "Columbus", region: "OH" });
    expect(shortDate("2027-04-04")).toEqual({ month: "Apr", day: "4", weekday: "Sun" });
    expect(km(4311)).toBe("4,311 km");
    expect(km(null)).toBe("—");
  });
});
