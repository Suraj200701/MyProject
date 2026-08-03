"use client";

import * as React from "react";
import { formatDistanceToNowStrict } from "date-fns";
import { toast } from "sonner";
import { Loader2, Send } from "lucide-react";

import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { errorMessage } from "@/lib/api/client";
import { useAddLeadNote } from "@/lib/api/queries";
import type { LeadNoteOut } from "@/lib/api/types";

/**
 * Notes for one lead.
 *
 * Notes arrive with the lead detail (`GET /leads/{id}` embeds them) and are
 * created via `POST /leads/{id}/notes`, which also writes a timeline activity —
 * so adding one refreshes both this list and the Lead Timeline card.
 *
 * `author_id` is a user id, and the backend has no endpoint to resolve arbitrary
 * user ids to names, so notes are attributed generically rather than inventing a
 * display name. (The previous version hardcoded "Suraj Gour" and "AI Assistant".)
 */
export function LeadNotes({ leadId, notes }: { leadId: string; notes: LeadNoteOut[] }) {
  const [draft, setDraft] = React.useState("");
  const addNote = useAddLeadNote(leadId);

  function submit() {
    const text = draft.trim();
    if (!text) return;
    addNote.mutate(text, {
      onSuccess: () => setDraft(""),
      onError: (error) => toast.error(errorMessage(error)),
    });
  }

  const ordered = React.useMemo(
    () => [...notes].sort((a, b) => +new Date(b.created_at) - +new Date(a.created_at)),
    [notes],
  );

  return (
    <div>
      <div className="flex gap-2">
        <Textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            // Ctrl/Cmd+Enter submits, matching the convention for a multi-line
            // field where plain Enter has to insert a newline.
            if ((e.metaKey || e.ctrlKey) && e.key === "Enter") submit();
          }}
          placeholder="Add a note about this lead..."
          className="min-h-[44px]"
          disabled={addNote.isPending}
        />
        <Button
          size="icon"
          className="shrink-0"
          onClick={submit}
          disabled={!draft.trim() || addNote.isPending}
        >
          {addNote.isPending ? <Loader2 className="size-4 animate-spin" /> : <Send className="size-4" />}
        </Button>
      </div>

      <div className="mt-4 space-y-3">
        {ordered.length === 0 ? (
          <p className="rounded-lg border border-dashed border-border px-3 py-6 text-center text-sm text-muted-foreground">
            No notes yet — add the first one above.
          </p>
        ) : (
          ordered.map((note) => (
            <div key={note.id} className="rounded-lg border border-border bg-surface-2/50 p-3">
              <div className="flex items-center justify-between">
                <p className="text-xs font-semibold text-foreground">
                  {note.author_id ? "Team member" : "System"}
                </p>
                <p className="text-[11px] text-muted-foreground">
                  {formatDistanceToNowStrict(new Date(note.created_at), { addSuffix: true })}
                </p>
              </div>
              <p className="mt-1.5 text-sm text-muted-foreground">{note.text}</p>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
