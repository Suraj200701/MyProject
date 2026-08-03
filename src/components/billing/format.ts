/**
 * Money formatting for the billing UI.
 *
 * The API reports amounts in minor units (cents) with an explicit currency, so
 * formatting happens once here instead of each component hardcoding a "$".
 */

/** `24900, "usd"` -> `"$249.00"`; whole amounts drop the ".00". */
export function formatMoney(amountCents: number, currency = "usd"): string {
  const value = amountCents / 100;
  const hasFraction = Math.round(amountCents) % 100 !== 0;
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency: currency.toUpperCase(),
      minimumFractionDigits: hasFraction ? 2 : 0,
      maximumFractionDigits: 2,
    }).format(value);
  } catch {
    // An unknown/blank currency code makes Intl throw; the number still matters
    // more than the symbol.
    return value.toFixed(hasFraction ? 2 : 0);
  }
}

/** Short absolute date for invoice rows: "1 Jul 2026". */
export function formatDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}
