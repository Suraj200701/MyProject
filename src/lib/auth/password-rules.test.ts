import { describe, expect, it } from "vitest";
import { passwordProblem } from "./password-rules";

describe("passwordProblem", () => {
  it("accepts a password meeting all three rules", () => {
    expect(passwordProblem("Password1")).toBeNull();
  });

  it("rejects anything shorter than 8 characters", () => {
    expect(passwordProblem("Pass1")).toBe("Password must be at least 8 characters long");
  });

  it("rejects a password with no uppercase letter", () => {
    expect(passwordProblem("password1")).toBe(
      "Password must contain at least one uppercase letter",
    );
  });

  it("rejects a password with no digit", () => {
    expect(passwordProblem("Passwordd")).toBe("Password must contain at least one digit");
  });

  /**
   * The case that motivated extracting this: long enough to pass signup's old
   * length-only check, but refused by the server for the missing uppercase.
   */
  it("rejects password123, which the signup form used to accept", () => {
    expect(passwordProblem("password123")).toBe(
      "Password must contain at least one uppercase letter",
    );
  });

  it("reports the first unmet rule, matching the backend's order", () => {
    // Short AND missing both an uppercase and a digit — length is reported.
    expect(passwordProblem("abc")).toBe("Password must be at least 8 characters long");
  });

  /**
   * The backend tests `c.isupper()` / `c.isdigit()`, which are Unicode-wide.
   * An ASCII-only `/[A-Z]/` or `/\d/` here would refuse passwords the server
   * accepts — the client disagreeing with the server in the direction the user
   * can't diagnose.
   */
  it("accepts a non-ASCII uppercase letter, as Python's isupper does", () => {
    expect(passwordProblem("Ünïcodé1")).toBeNull();
    expect(passwordProblem("Ω12345678")).toBeNull();
  });

  it("accepts a non-ASCII decimal digit, as Python's isdigit does", () => {
    expect(passwordProblem("Password١")).toBeNull();
  });

  it("does not count titlecase as uppercase, matching Python", () => {
    // U+01C5 is category Lt; 'ǅ'.isupper() is False in Python too.
    expect(passwordProblem("ǅaaaaaa1")).toBe(
      "Password must contain at least one uppercase letter",
    );
  });

  /**
   * JS `.length` counts UTF-16 units and Python's len() counts code points, so
   * a naive check would pass this at 10 and let the server reject it at 5.
   */
  it("measures length in code points, so astral characters count once", () => {
    expect(passwordProblem("🔑🔑🔑🔑🔑")).toBe("Password must be at least 8 characters long");
  });

  it("treats an empty password as too short rather than throwing", () => {
    expect(passwordProblem("")).toBe("Password must be at least 8 characters long");
  });
});
