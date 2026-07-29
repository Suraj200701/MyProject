import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatNumber(n: number) {
  return new Intl.NumberFormat("en-US", { notation: n >= 10000 ? "compact" : "standard" }).format(n);
}

export function formatCurrency(n: number, currency = "USD") {
  return new Intl.NumberFormat("en-US", { style: "currency", currency, maximumFractionDigits: 0 }).format(n);
}

let idCounter = 0;

/** Deterministic, collision-free id generator for client-only mock records (avoids impure Date.now()/Math.random() during render). */
export function nextId(prefix: string) {
  idCounter += 1;
  return `${prefix}-${idCounter}`;
}
