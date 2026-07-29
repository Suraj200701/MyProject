"use client";

import { StepLayout } from "@/components/onboarding/StepLayout";
import { OptionCard } from "@/components/onboarding/OptionCard";
import { BUSINESS_TYPES } from "@/components/onboarding/constants";

interface StepBusinessTypeProps {
  value: string | null;
  onChange: (value: string) => void;
  onNext: () => void;
  onBack: () => void;
}

export function StepBusinessType({ value, onChange, onNext, onBack }: StepBusinessTypeProps) {
  return (
    <StepLayout
      title="What is your business?"
      subtitle="This helps us tailor lead recommendations to your workflow."
      onBack={onBack}
      onNext={onNext}
      nextDisabled={!value}
    >
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {BUSINESS_TYPES.map((option) => {
          const Icon = option.icon;
          return (
            <OptionCard
              key={option.value}
              label={option.label}
              description={option.description}
              icon={<Icon className="size-5" />}
              selected={value === option.value}
              onClick={() => onChange(option.value)}
            />
          );
        })}
      </div>
    </StepLayout>
  );
}
