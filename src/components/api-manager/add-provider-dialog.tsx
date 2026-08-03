"use client";

import { useState } from "react";
import { Info, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

/**
 * "Add Provider".
 *
 * This used to be a name + API key form that waited 700ms and toasted
 * "<name> connected successfully" — no request was made and nothing was stored.
 * The backend has no endpoint to create a provider or set its credentials
 * (`ApiProvider.api_key_encrypted` exists but is deliberately unreachable from
 * the API), so a working form is not possible here.
 *
 * Rather than keep a form that silently discards a pasted API key — the worst
 * outcome, since the user would believe a secret had been saved — the dialog now
 * explains where credentials actually go. The trigger button stays so the page
 * header is unchanged.
 */
export function AddProviderDialog() {
  const [open, setOpen] = useState(false);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="gradient" size="sm">
          <Plus className="size-4" />
          Add Provider
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Adding a provider</DialogTitle>
          <DialogDescription>
            Providers are configured on the server, not from the browser.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3 text-sm text-muted-foreground">
          <p>
            The provider catalogue is seeded by the backend, and credentials are read from its
            environment so that API keys never travel to or from the browser.
          </p>
          <ol className="list-decimal space-y-1.5 pl-5">
            <li>
              Set the provider&apos;s variables in{" "}
              <code className="rounded bg-surface-2 px-1 py-0.5 font-mono text-xs">backend/.env</code>{" "}
              — for example{" "}
              <code className="rounded bg-surface-2 px-1 py-0.5 font-mono text-xs">
                GOOGLE_MAPS_API_KEY
              </code>
              ,{" "}
              <code className="rounded bg-surface-2 px-1 py-0.5 font-mono text-xs">
                MAPPLS_CLIENT_ID
              </code>{" "}
              /{" "}
              <code className="rounded bg-surface-2 px-1 py-0.5 font-mono text-xs">
                MAPPLS_CLIENT_SECRET
              </code>
              , or{" "}
              <code className="rounded bg-surface-2 px-1 py-0.5 font-mono text-xs">
                BING_SEARCH_API_KEY
              </code>
              .
            </li>
            <li>Restart the API so the new settings are picked up.</li>
            <li>
              Run a search — the provider appears in the results panel with a real status and lead
              count.
            </li>
          </ol>
          <p className="flex items-start gap-1.5 text-xs">
            <Info className="mt-0.5 size-3.5 shrink-0" />
            A provider without credentials is skipped during a search and costs no credits, so it is
            safe to leave unconfigured.
          </p>
        </div>

        <DialogFooter>
          <Button variant="secondary" size="sm" onClick={() => setOpen(false)}>
            Got it
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
