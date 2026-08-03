"use client";

import * as React from "react";
import { toast } from "sonner";
import { CheckCircle2, ExternalLink, Info, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useClearProviderCredentials,
  useProviderCredentials,
  useSetProviderCredentials,
} from "@/lib/api/queries";
import { ApiError } from "@/lib/api/client";
import type { ProviderCredentialStatusOut } from "@/lib/api/types";

const SOURCE_LABEL: Record<ProviderCredentialStatusOut["source"], string> = {
  workspace: "Saved here",
  environment: "From backend .env",
  unset: "Not configured",
  none_required: "No credentials needed",
};

const SOURCE_VARIANT: Record<
  ProviderCredentialStatusOut["source"],
  "success" | "outline" | "warning"
> = {
  workspace: "success",
  environment: "outline",
  unset: "warning",
  none_required: "outline",
};

/**
 * Credentials tab for one provider.
 *
 * Credentials are write-only: the backend encrypts them and never returns them,
 * so this form shows *whether* each field is set and lets you replace or clear
 * it — it can never pre-fill an existing value. Leaving a field blank keeps the
 * stored value, which is what makes rotating one half of a pair possible.
 *
 * `useProviderCredentials` requires the `api_keys.manage` permission. A role
 * without it gets a 403, which renders as an explanatory line rather than an
 * error state — not being allowed to manage keys is a normal condition, not a
 * failure.
 */
export function CredentialsForm({ providerId }: { providerId: string }) {
  const { data, isPending, isError, error } = useProviderCredentials();
  const save = useSetProviderCredentials();
  const clear = useClearProviderCredentials();

  const [keyValue, setKeyValue] = React.useState("");
  const [secretValue, setSecretValue] = React.useState("");

  const status = data?.find((entry) => entry.provider_id === providerId);

  if (isPending) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-4 w-48" />
        <Skeleton className="h-9 w-full" />
        <Skeleton className="h-9 w-full" />
      </div>
    );
  }

  if (isError) {
    const forbidden = error instanceof ApiError && error.isForbidden;
    return (
      <p className="flex items-start gap-1.5 text-xs text-muted-foreground">
        <Info className="mt-0.5 size-3 shrink-0" />
        {forbidden
          ? "Your role can't manage provider credentials. Ask an owner or admin to set them."
          : `Couldn't load credential status: ${error instanceof Error ? error.message : "unknown error"}`}
      </p>
    );
  }

  if (!status || status.source === "none_required" || !status.key) {
    return (
      <p className="flex items-start gap-1.5 text-xs text-muted-foreground">
        <Info className="mt-0.5 size-3 shrink-0" />
        This provider doesn&apos;t take credentials — it works out of the box.
      </p>
    );
  }

  const busy = save.isPending || clear.isPending;
  const nothingEntered = !keyValue.trim() && !secretValue.trim();

  function submit(event: React.FormEvent) {
    event.preventDefault();
    save.mutate(
      {
        providerId,
        // Omit empty fields so a blank input means "leave unchanged" rather
        // than "overwrite with an empty string".
        ...(keyValue.trim() ? { api_key: keyValue.trim() } : {}),
        ...(secretValue.trim() ? { api_secret: secretValue.trim() } : {}),
      },
      {
        onSuccess: () => {
          setKeyValue("");
          setSecretValue("");
          toast.success("Credentials saved", {
            description: "They take effect on the next search — no restart needed.",
          });
        },
        onError: (mutationError) => toast.error(mutationError.message),
      },
    );
  }

  return (
    <form onSubmit={submit} className="space-y-3">
      <div className="flex items-center gap-2">
        <Badge variant={SOURCE_VARIANT[status.source]}>{SOURCE_LABEL[status.source]}</Badge>
        {status.help_url ? (
          <a
            href={status.help_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground"
          >
            Where do I get this? <ExternalLink className="size-3" />
          </a>
        ) : null}
      </div>

      <div className="space-y-1.5">
        <Label htmlFor={`cred-key-${providerId}`} className="flex items-center gap-1.5 text-xs">
          {status.key.label}
          {status.key.is_set ? <CheckCircle2 className="size-3 text-success" /> : null}
        </Label>
        <Input
          id={`cred-key-${providerId}`}
          type="password"
          autoComplete="off"
          spellCheck={false}
          disabled={busy}
          value={keyValue}
          onChange={(e) => setKeyValue(e.target.value)}
          placeholder={status.key.is_set ? "Saved — enter a new value to replace" : "Paste value"}
        />
      </div>

      {status.secret ? (
        <div className="space-y-1.5">
          <Label htmlFor={`cred-secret-${providerId}`} className="flex items-center gap-1.5 text-xs">
            {status.secret.label}
            {status.secret.is_set ? <CheckCircle2 className="size-3 text-success" /> : null}
          </Label>
          <Input
            id={`cred-secret-${providerId}`}
            type="password"
            autoComplete="off"
            spellCheck={false}
            disabled={busy}
            value={secretValue}
            onChange={(e) => setSecretValue(e.target.value)}
            placeholder={
              status.secret.is_set ? "Saved — enter a new value to replace" : "Paste value"
            }
          />
        </div>
      ) : null}

      <div className="flex items-center gap-2 pt-1">
        <Button type="submit" size="sm" disabled={busy || nothingEntered}>
          {save.isPending ? <Loader2 className="size-3.5 animate-spin" /> : null}
          Save credentials
        </Button>
        {status.source === "workspace" ? (
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={busy}
            onClick={() =>
              clear.mutate(providerId, {
                onSuccess: () =>
                  toast.success("Stored credentials removed", {
                    description: "This provider now falls back to the backend .env values.",
                  }),
                onError: (mutationError) => toast.error(mutationError.message),
              })
            }
          >
            Remove
          </Button>
        ) : null}
      </div>

      <p className="flex items-start gap-1.5 text-[11px] text-muted-foreground">
        <Info className="mt-0.5 size-3 shrink-0" />
        Stored encrypted on the server and never sent back to the browser — not even masked. If
        nothing is saved here, the backend&apos;s{" "}
        <code className="rounded bg-surface-2 px-1 font-mono">{status.key.env_var}</code>
        {status.secret ? (
          <>
            {" / "}
            <code className="rounded bg-surface-2 px-1 font-mono">{status.secret.env_var}</code>
          </>
        ) : null}{" "}
        is used instead. A provider with neither is skipped during a search rather than charged for.
      </p>
    </form>
  );
}
