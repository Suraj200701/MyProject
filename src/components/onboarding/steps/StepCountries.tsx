"use client";

import { StepLayout } from "@/components/onboarding/StepLayout";
import { ChipToggle } from "@/components/onboarding/ChipToggle";
import { COUNTRIES } from "@/components/onboarding/constants";

interface StepCountriesProps {
  value: string[];
  onToggle: (value: string) => void;
  onNext: () => void;
  onBack: () => void;
}

export function StepCountries({ value, onToggle, onNext, onBack }: StepCountriesProps) {
  return (
    <StepLayout
      title="Which countries do you target?"
      subtitle="Select every market you'd like to source leads from."
      onBack={onBack}
      onNext={onNext}
      nextDisabled={value.length === 0}
      hint={value.length > 0 ? `${value.length} selected` : undefined}
    >
      <div className="flex flex-wrap gap-2.5">
        {COUNTRIES.map((country) => (
          <ChipToggle
            key={country.value}
            label={country.label}
            prefix={<span>{country.flag}</span>}
            selected={value.includes(country.value)}
            onClick={() => onToggle(country.value)}
          />
        ))}
      </div>
    </StepLayout>
  );
}
