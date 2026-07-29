"use client";

import * as React from "react";
import { X } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export function ChipInput({
  values,
  onChange,
  placeholder,
  className,
}: {
  values: string[];
  onChange: (values: string[]) => void;
  placeholder?: string;
  className?: string;
}) {
  const [draft, setDraft] = React.useState("");

  function commit() {
    const trimmed = draft.trim();
    if (trimmed && !values.some((v) => v.toLowerCase() === trimmed.toLowerCase())) {
      onChange([...values, trimmed]);
    }
    setDraft("");
  }

  function remove(value: string) {
    onChange(values.filter((v) => v !== value));
  }

  return (
    <div className={cn("space-y-2", className)}>
      <Input
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            commit();
          } else if (e.key === "Backspace" && draft === "" && values.length > 0) {
            remove(values[values.length - 1]);
          }
        }}
        placeholder={placeholder}
      />
      {values.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {values.map((value) => (
            <Badge key={value} variant="primary" className="pl-2.5 pr-1">
              {value}
              <button
                type="button"
                onClick={() => remove(value)}
                className="ml-0.5 rounded-full p-0.5 hover:bg-primary/20 transition-colors cursor-pointer"
                aria-label={`Remove ${value}`}
              >
                <X className="size-3" />
              </button>
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}
