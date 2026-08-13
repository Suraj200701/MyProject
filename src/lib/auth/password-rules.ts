/**
 * The one client-side copy of the server's password policy.
 *
 * The rules themselves live in `_validate_password_strength`
 * (backend/schemas/user.py) and are enforced there — this exists so the user
 * finds out before a request is spent, not after. Two call sites depended on
 * that and disagreed: signup checked length alone, so `password123` passed the
 * form and came back as a 400 from the server.
 *
 * Keep the messages identical to the backend's ValueError strings. When the
 * same rule is stated in two voices, the second one reads as a different rule.
 *
 * ## Why the regexes are Unicode-aware
 *
 * The backend tests `c.isupper()` and `c.isdigit()`, which are Unicode-wide:
 * Python accepts `Ünïcodé1` and `Password١`. The obvious `/[A-Z]/` and `/\d/`
 * are ASCII-only and would reject both — the client refusing a password the
 * server would take. That is the worse direction to be wrong in: a server
 * rejection is at least explained by the server, while a form that silently
 * disagrees leaves the user retyping a password that was fine.
 *
 * `\p{Lu}` matches `str.isupper()` exactly — both are false for titlecase
 * (U+01C5 ǅ is Lt, and Python reports it as not upper). `\p{Nd}` covers every
 * decimal digit in every script; the only gap left is `isdigit()`'s extra
 * acceptance of superscripts (² ³ ¹, category No), so a password whose only
 * digit is a superscript is refused here and would have been allowed. That is
 * strictness in a corner no real password reaches, and closing it would mean
 * enumerating Numeric_Type=Digit by hand.
 */

export const PASSWORD_MIN_LENGTH = 8;

/** Human-readable summary of the rules, for helper text under the field. */
export const PASSWORD_RULES_HINT =
  "At least 8 characters, with one uppercase letter and one digit.";

/**
 * Returns the first unmet requirement, or null when the password is acceptable.
 *
 * Order matches the backend's, so the message a user sees here is the message
 * they would have seen from the server.
 */
export function passwordProblem(value: string): string | null {
  // Code points, not UTF-16 units, to match Python's len(). `.length` counts a
  // surrogate pair as 2, so "🔑🔑🔑🔑🔑" would pass here at 10 and then fail
  // server-side at 5.
  if ([...value].length < PASSWORD_MIN_LENGTH) {
    return "Password must be at least 8 characters long";
  }
  if (!/\p{Lu}/u.test(value)) {
    return "Password must contain at least one uppercase letter";
  }
  if (!/\p{Nd}/u.test(value)) {
    return "Password must contain at least one digit";
  }
  return null;
}
