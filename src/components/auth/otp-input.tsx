"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

interface OtpInputProps {
  length?: number;
  value: string[];
  onChange: (value: string[]) => void;
  onComplete?: (code: string) => void;
  disabled?: boolean;
}

export function OtpInput({ length = 6, value, onChange, onComplete, disabled }: OtpInputProps) {
  const inputRefs = React.useRef<Array<HTMLInputElement | null>>([]);

  const setDigit = (index: number, digit: string) => {
    const next = [...value];
    next[index] = digit;
    onChange(next);

    if (digit && next.every((d) => d.length === 1)) {
      onComplete?.(next.join(""));
    }
  };

  const handleChange = (index: number, raw: string) => {
    const digit = raw.replace(/[^0-9]/g, "").slice(-1);
    setDigit(index, digit);
    if (digit && index < length - 1) {
      inputRefs.current[index + 1]?.focus();
    }
  };

  const handleKeyDown = (index: number, e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Backspace") {
      if (value[index]) {
        setDigit(index, "");
      } else if (index > 0) {
        inputRefs.current[index - 1]?.focus();
        setDigit(index - 1, "");
      }
    } else if (e.key === "ArrowLeft" && index > 0) {
      inputRefs.current[index - 1]?.focus();
    } else if (e.key === "ArrowRight" && index < length - 1) {
      inputRefs.current[index + 1]?.focus();
    }
  };

  const handlePaste = (e: React.ClipboardEvent<HTMLInputElement>) => {
    e.preventDefault();
    const pasted = e.clipboardData.getData("text").replace(/[^0-9]/g, "").slice(0, length);
    if (!pasted) return;
    const next = Array.from({ length }, (_, i) => pasted[i] ?? "");
    onChange(next);
    const lastFilled = Math.min(pasted.length, length) - 1;
    inputRefs.current[Math.max(lastFilled, 0)]?.focus();
    if (pasted.length === length) {
      onComplete?.(pasted);
    }
  };

  return (
    <div className="flex items-center justify-between gap-2">
      {Array.from({ length }).map((_, i) => (
        <input
          key={i}
          ref={(el) => {
            inputRefs.current[i] = el;
          }}
          type="text"
          inputMode="numeric"
          autoComplete={i === 0 ? "one-time-code" : "off"}
          maxLength={1}
          disabled={disabled}
          value={value[i] ?? ""}
          onChange={(e) => handleChange(i, e.target.value)}
          onKeyDown={(e) => handleKeyDown(i, e)}
          onPaste={handlePaste}
          className={cn(
            "h-12 w-11 rounded-lg border border-border bg-surface-2/60 text-center text-lg font-semibold text-foreground shadow-xs outline-none transition-colors sm:w-12",
            "focus-visible:border-primary/50 focus-visible:ring-2 focus-visible:ring-ring",
            "disabled:cursor-not-allowed disabled:opacity-50",
          )}
        />
      ))}
    </div>
  );
}
