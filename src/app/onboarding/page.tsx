"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";

import { ProgressHeader } from "@/components/onboarding/ProgressHeader";
import { StepWelcome } from "@/components/onboarding/steps/StepWelcome";
import { StepBusinessType } from "@/components/onboarding/steps/StepBusinessType";
import { StepIndustry } from "@/components/onboarding/steps/StepIndustry";
import { StepDataSources } from "@/components/onboarding/steps/StepDataSources";
import { StepCountries } from "@/components/onboarding/steps/StepCountries";
import { StepVolume } from "@/components/onboarding/steps/StepVolume";
import { StepTeamSize } from "@/components/onboarding/steps/StepTeamSize";
import { StepFinalizing } from "@/components/onboarding/steps/StepFinalizing";
import { initialAnswers, type OnboardingAnswers } from "@/components/onboarding/constants";

const TOTAL_PROGRESS_STEPS = 7;
const FINALIZING_STEP = 7;

function toggleValue(list: string[], value: string) {
  return list.includes(value) ? list.filter((item) => item !== value) : [...list, value];
}

export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = React.useState(0);
  const [answers, setAnswers] = React.useState<OnboardingAnswers>(initialAnswers);

  const goNext = React.useCallback(() => setStep((s) => Math.min(s + 1, FINALIZING_STEP)), []);
  const goBack = React.useCallback(() => setStep((s) => Math.max(s - 1, 0)), []);

  const updateAnswer = <K extends keyof OnboardingAnswers>(key: K, value: OnboardingAnswers[K]) => {
    setAnswers((prev) => ({ ...prev, [key]: value }));
  };

  const toggleAnswer = (key: "industries" | "dataSources" | "countries", value: string) => {
    setAnswers((prev) => ({ ...prev, [key]: toggleValue(prev[key], value) }));
  };

  const showProgress = step >= 0 && step < FINALIZING_STEP;

  return (
    <div className="relative flex min-h-screen w-full items-center justify-center overflow-hidden bg-background px-4 py-10">
      <div className="bg-grid pointer-events-none absolute inset-0 opacity-60" />
      <div className="pointer-events-none absolute left-1/2 top-0 h-[420px] w-[720px] -translate-x-1/2 rounded-full bg-primary/20 blur-[120px]" />

      <div className="relative z-10 w-full max-w-[640px]">
        <div className="glass-strong rounded-2xl p-6 shadow-2xl sm:p-10">
          {showProgress ? <ProgressHeader current={step + 1} total={TOTAL_PROGRESS_STEPS} /> : null}

          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={step}
              initial={{ opacity: 0, x: 24 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -24 }}
              transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
            >
              {step === 0 ? <StepWelcome onNext={goNext} /> : null}

              {step === 1 ? (
                <StepBusinessType
                  value={answers.businessType}
                  onChange={(value) => updateAnswer("businessType", value)}
                  onNext={goNext}
                  onBack={goBack}
                />
              ) : null}

              {step === 2 ? (
                <StepIndustry
                  value={answers.industries}
                  onToggle={(value) => toggleAnswer("industries", value)}
                  onNext={goNext}
                  onBack={goBack}
                />
              ) : null}

              {step === 3 ? (
                <StepDataSources
                  value={answers.dataSources}
                  onToggle={(value) => toggleAnswer("dataSources", value)}
                  onNext={goNext}
                  onBack={goBack}
                />
              ) : null}

              {step === 4 ? (
                <StepCountries
                  value={answers.countries}
                  onToggle={(value) => toggleAnswer("countries", value)}
                  onNext={goNext}
                  onBack={goBack}
                />
              ) : null}

              {step === 5 ? (
                <StepVolume
                  value={answers.volume}
                  onChange={(value) => updateAnswer("volume", value)}
                  onNext={goNext}
                  onBack={goBack}
                />
              ) : null}

              {step === 6 ? (
                <StepTeamSize
                  value={answers.teamSize}
                  onChange={(value) => updateAnswer("teamSize", value)}
                  onNext={goNext}
                  onBack={goBack}
                />
              ) : null}

              {step === FINALIZING_STEP ? (
                <StepFinalizing answers={answers} onFinish={() => router.replace("/dashboard")} />
              ) : null}
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
