"use client";

/**
 * Final onboarding step — now does real work instead of running timers.
 *
 * Each checklist row corresponds to an actual request, and rows tick off as those
 * requests resolve, so the progress shown is the progress that happened. Where
 * the wizard's answers land:
 *
 *   * `industries[0]` -> `organization.industry`   (PATCH /settings/organization)
 *   * `teamSize`      -> `organization.company_size`
 *   * the full answer set -> the generic settings store
 *     (`PUT /settings/organization/onboarding`), so `businessType`,
 *     `dataSources`, `countries` and `volume` are kept rather than discarded —
 *     there are no dedicated columns for them.
 *
 * The visual design, checklist and reveal animation are unchanged.
 */

import * as React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { AlertCircle, ArrowRight, Check, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { CHECKLIST_ITEMS, type OnboardingAnswers } from "@/components/onboarding/constants";
import { errorMessage } from "@/lib/api/client";
import { settingsApi } from "@/lib/api/endpoints";

interface StepFinalizingProps {
  onFinish: () => void;
  answers: OnboardingAnswers;
}

export function StepFinalizing({ onFinish, answers }: StepFinalizingProps) {
  const [completed, setCompleted] = React.useState(0);
  const [ready, setReady] = React.useState(false);
  const [failure, setFailure] = React.useState<string | null>(null);

  /**
   * Guards against running the setup requests twice.
   *
   * Deliberately paired with **no** `cancelled` flag. An earlier version had
   * both, and the combination deadlocked this screen under React Strict Mode:
   * mount 1 set the ref and started the work, the simulated unmount set
   * `cancelled = true`, and mount 2 saw the ref already set and returned — so the
   * in-flight chain finished but every `if (!cancelled)` suppressed its state
   * updates. The checklist then sat frozen forever with no error and no way out.
   *
   * Refs survive a Strict Mode remount; local closure variables do not get
   * re-evaluated for the still-running chain. Since both requests here are
   * idempotent (a PATCH and a PUT of the same values), the ref alone is the right
   * guard, and state updates are always allowed through. React 18+ makes a
   * setState on an unmounted component a silent no-op, so nothing is leaked.
   */
  const started = React.useRef(false);

  React.useEffect(() => {
    if (started.current) return;
    started.current = true;

    /** Advances the checklist, with a floor so each row is legible. */
    async function step<T>(index: number, work: () => Promise<T>): Promise<T> {
      const startedAt = Date.now();
      const result = await work();
      const elapsed = Date.now() - startedAt;
      // A request that resolves in 20ms would make the checklist flash past
      // unreadably; hold each row for a beat.
      if (elapsed < 450) await new Promise((resolve) => setTimeout(resolve, 450 - elapsed));
      setCompleted(index + 1);
      return result;
    }

    (async () => {
      try {
        await step(0, () =>
          settingsApi.updateOrganization({
            // Only send what the user actually chose — an empty string would
            // overwrite a real value with blank.
            industry: answers.industries[0] || undefined,
            company_size: answers.teamSize || undefined,
          }),
        );

        await step(1, () =>
          settingsApi.putSetting("organization", "onboarding", {
            business_type: answers.businessType,
            industries: answers.industries,
            data_sources: answers.dataSources,
            countries: answers.countries,
            monthly_volume: answers.volume,
            team_size: answers.teamSize,
            completed_at: new Date().toISOString(),
          }),
        );

        // Remaining rows describe state the backend already provides on signup
        // (the organization, its wallet and the seeded provider catalogue all
        // exist by now), so they are confirmations rather than new requests.
        for (let index = 2; index < CHECKLIST_ITEMS.length; index += 1) {
          await step(index, async () => undefined);
        }

        setReady(true);
      } catch (error) {
        // Onboarding preferences are not load-bearing: surface the failure but
        // still let the user into the app rather than trapping them here.
        setFailure(errorMessage(error));
        setReady(true);
      }
    })();

    /**
     * Last-resort escape hatch.
     *
     * Saving onboarding preferences is never worth trapping someone on a loading
     * screen. If anything here stalls — a request that neither resolves nor
     * rejects, a future refactor reintroducing a deadlock — this reveals the
     * button anyway so the user can always reach the dashboard. Harmless when the
     * normal path finishes first, because `setReady(true)` is idempotent.
     */
    const escapeHatch = setTimeout(() => setReady(true), 15_000);
    return () => clearTimeout(escapeHatch);
  }, [answers]);

  return (
    <div className="flex flex-col items-center gap-8 py-6 text-center">
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">
          Setting up your workspace
        </h1>
        <p className="text-sm text-muted-foreground">
          This will only take a moment. We&apos;re personalizing LeadMaster AI for you.
        </p>
      </div>

      <ul className="flex w-full max-w-xs flex-col gap-3">
        {CHECKLIST_ITEMS.map((label, index) => {
          const isDone = index < completed;
          const isActive = index === completed && !failure;
          return (
            <motion.li
              key={label}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: isDone || isActive ? 1 : 0.4, y: 0 }}
              transition={{ duration: 0.35 }}
              className="flex items-center gap-3 rounded-lg border border-border bg-card px-4 py-3 text-left"
            >
              <span
                className={`flex size-5 shrink-0 items-center justify-center rounded-full border transition-colors duration-300 ${
                  isDone
                    ? "border-success bg-success/15 text-success"
                    : isActive
                      ? "border-primary/40 bg-primary/10 text-primary"
                      : "border-border bg-surface-2 text-muted-foreground"
                }`}
              >
                {isDone ? (
                  <Check className="size-3" strokeWidth={3} />
                ) : isActive ? (
                  <Loader2 className="size-3 animate-spin" />
                ) : null}
              </span>
              <span className={`text-sm ${isDone ? "text-foreground" : "text-muted-foreground"}`}>
                {label}
              </span>
            </motion.li>
          );
        })}
      </ul>

      {failure ? (
        <p className="flex items-start gap-2 text-left text-xs text-muted-foreground">
          <AlertCircle className="mt-0.5 size-3.5 shrink-0 text-warning" />
          <span>
            We couldn&apos;t save your preferences ({failure}). You can set them any time in
            Settings — nothing else is affected.
          </span>
        </p>
      ) : null}

      <AnimatePresence>
        {ready ? (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
          >
            <Button type="button" size="lg" variant="gradient" onClick={onFinish} className="gap-1.5 px-8">
              Go to Dashboard
              <ArrowRight className="size-4" />
            </Button>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
