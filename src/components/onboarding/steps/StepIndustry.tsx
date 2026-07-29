"use client";

import { StepLayout } from "@/components/onboarding/StepLayout";
import { ChipToggle } from "@/components/onboarding/ChipToggle";
import { INDUSTRIES } from "@/components/onboarding/constants";

interface StepIndustryProps {
  value: string[];
  onToggle: (value: string) => void;
  onNext: () => void;
  onBack: () => void;
}

export function StepIndustry({ value, onToggle, onNext, onBack }: StepIndustryProps) {
  return (
    <StepLayout
      title="Which industry do you serve?"
      subtitle="Select all that apply — this fine-tunes your lead search filters."
      onBack={onBack}
      onNext={onNext}
      nextDisabled={value.length === 0}
      hint={value.length > 0 ? `${value.length} selected` : undefined}
    >
      <div className="flex flex-wrap gap-2.5">
        {INDUSTRIES.map((industry) => (
          <ChipToggle
            key={industry}
            label={industry}
            selected={value.includes(industry)}
            onClick={() => onToggle(industry)}
          />
        ))}
      </div>
    </StepLayout>
  );
}
