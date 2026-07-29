"use client";

import { Gauge } from "lucide-react";
import { StepLayout } from "@/components/onboarding/StepLayout";
import { OptionCard } from "@/components/onboarding/OptionCard";
import { VOLUME_OPTIONS } from "@/components/onboarding/constants";

interface StepVolumeProps {
  value: string | null;
  onChange: (value: string) => void;
  onNext: () => void;
  onBack: () => void;
}

export function StepVolume({ value, onChange, onNext, onBack }: StepVolumeProps) {
  return (
    <StepLayout
      title="Monthly lead requirements?"
      subtitle="Roughly how many leads do you need to source each month?"
      onBack={onBack}
      onNext={onNext}
      nextDisabled={!value}
    >
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {VOLUME_OPTIONS.map((option) => (
          <OptionCard
            key={option.value}
            label={option.label}
            description={option.description}
            icon={<Gauge className="size-5" />}
            selected={value === option.value}
            onClick={() => onChange(option.value)}
          />
        ))}
      </div>
    </StepLayout>
  );
}
