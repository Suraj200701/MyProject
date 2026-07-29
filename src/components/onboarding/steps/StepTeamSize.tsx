"use client";

import { Users } from "lucide-react";
import { StepLayout } from "@/components/onboarding/StepLayout";
import { OptionCard } from "@/components/onboarding/OptionCard";
import { TEAM_SIZE_OPTIONS } from "@/components/onboarding/constants";

interface StepTeamSizeProps {
  value: string | null;
  onChange: (value: string) => void;
  onNext: () => void;
  onBack: () => void;
}

export function StepTeamSize({ value, onChange, onNext, onBack }: StepTeamSizeProps) {
  return (
    <StepLayout
      title="What's your team size?"
      subtitle="We'll tailor collaboration features and seat suggestions accordingly."
      onBack={onBack}
      onNext={onNext}
      nextDisabled={!value}
      nextLabel="Finish setup"
    >
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {TEAM_SIZE_OPTIONS.map((option) => (
          <OptionCard
            key={option.value}
            label={option.label}
            description={option.description}
            icon={<Users className="size-5" />}
            selected={value === option.value}
            onClick={() => onChange(option.value)}
          />
        ))}
      </div>
    </StepLayout>
  );
}
