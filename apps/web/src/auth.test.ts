import { jwtExpiry } from "./auth";

const b64url = (o: object) => btoa(JSON.stringify(o)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");

describe("jwtExpiry", () => {
  it("reads exp (seconds) from a JWT as milliseconds", () => {
    expect(jwtExpiry(`${b64url({ alg: "EdDSA" })}.${b64url({ sub: "u1", exp: 1_800_000_000 })}.sig`)).toBe(1_800_000_000_000);
  });

  it("treats anything unreadable as already expired", () => {
    expect(jwtExpiry("not-a-jwt")).toBe(0);
    expect(jwtExpiry(`${b64url({})}.${b64url({ sub: "u1" })}.sig`)).toBe(0);
  });
});
