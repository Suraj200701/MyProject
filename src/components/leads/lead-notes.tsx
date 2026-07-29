"use client";

import * as React from "react";
import { formatDistanceToNowStrict } from "date-fns";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Send } from "lucide-react";

interface Note {
  id: string;
  author: string;
  text: string;
  createdAt: string;
}

export function LeadNotes({ leadId }: { leadId: string }) {
  const [notes, setNotes] = React.useState<Note[]>([
    {
      id: `${leadId}-n1`,
      author: "Suraj Gour",
      text: "Reached out via email — waiting on a response before following up by phone.",
      createdAt: new Date(Date.now() - 2 * 86400000).toISOString(),
    },
    {
      id: `${leadId}-n2`,
      author: "AI Assistant",
      text: "Website traffic signals suggest active expansion — good time to re-engage.",
      createdAt: new Date(Date.now() - 6 * 3600000).toISOString(),
    },
  ]);
  const [draft, setDraft] = React.useState("");

  function addNote() {
    if (!draft.trim()) return;
    setNotes((prev) => [
      { id: `${leadId}-${Date.now()}`, author: "You", text: draft.trim(), createdAt: new Date().toISOString() },
      ...prev,
    ]);
    setDraft("");
  }

  return (
    <div>
      <div className="flex gap-2">
        <Textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Add a note about this lead..."
          className="min-h-[44px]"
        />
        <Button size="icon" className="shrink-0" onClick={addNote} disabled={!draft.trim()}>
          <Send className="size-4" />
        </Button>
      </div>

      <div className="mt-4 space-y-3">
        {notes.map((note) => (
          <div key={note.id} className="rounded-lg border border-border bg-surface-2/50 p-3">
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold text-foreground">{note.author}</p>
              <p className="text-[11px] text-muted-foreground">
                {formatDistanceToNowStrict(new Date(note.createdAt), { addSuffix: true })}
              </p>
            </div>
            <p className="mt-1.5 text-sm text-muted-foreground">{note.text}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
