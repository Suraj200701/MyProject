"use client";

import { StepLayout } from "@/components/onboarding/StepLayout";
import { OptionCard } from "@/components/onboarding/OptionCard";
import { DATA_SOURCES } from "@/components/onboarding/constants";

interface StepDataSourcesProps {
  value: string[];
  onToggle: (value: string) => void;
  onNext: () => void;
  onBack: () => void;
}

export function StepDataSources({ value, onToggle, onNext, onBack }: StepDataSourcesProps) {
  return (
    <StepLayout
      title="Which data sources do you use?"
      subtitle="Pick the APIs and platforms you'd like to connect. You can change this later."
      onBack={onBack}
      onNext={onNext}
      nextDisabled={value.length === 0}
      hint={value.length > 0 ? `${value.length} selected` : undefined}
    >
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {DATA_SOURCES.map((source) => (
          <OptionCard
            key={source.value}
            label={source.label}
            icon={<span className="text-lg leading-none">{source.emoji}</span>}
            selected={value.includes(source.value)}
            onClick={() => onToggle(source.value)}
          />
        ))}
      </div>
    </StepLayout>
  );
}
