"use client";

import { AnimatePresence, motion } from "framer-motion";
import { toast } from "sonner";
import { ListPlus, Download, X, CheckSquare } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { ResultCard } from "@/components/search/result-card";
import { EmptyState } from "@/components/shared/empty-state";
import { SearchX } from "lucide-react";
import type { Lead } from "@/lib/types";

export function ResultsGrid({
  leads,
  selectedIds,
  onToggleSelect,
  onSelectAll,
  onClearSelection,
}: {
  leads: Lead[];
  selectedIds: string[];
  onToggleSelect: (id: string) => void;
  onSelectAll: () => void;
  onClearSelection: () => void;
}) {
  const allSelected = leads.length > 0 && selectedIds.length === leads.length;

  if (leads.length === 0) {
    return (
      <EmptyState
        icon={SearchX}
        title="No leads matched this search"
        description="Try adjusting your filters or broadening the search query."
      />
    );
  }

  return (
    <div className="space-y-4 pb-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Checkbox
            checked={allSelected}
            onCheckedChange={() => (allSelected ? onClearSelection() : onSelectAll())}
            aria-label="Select all results"
          />
          <span className="text-sm text-muted-foreground">
            <span className="font-medium text-foreground">{leads.length}</span> leads found
          </span>
        </div>
        {selectedIds.length > 0 && (
          <span className="text-xs text-muted-foreground">{selectedIds.length} selected</span>
        )}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
        {leads.map((lead, i) => (
          <ResultCard
            key={lead.id}
            lead={lead}
            index={i}
            selected={selectedIds.includes(lead.id)}
            onToggleSelect={onToggleSelect}
          />
        ))}
      </div>

      <AnimatePresence>
        {selectedIds.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 24 }}
            transition={{ duration: 0.25, ease: "easeOut" }}
            className="fixed inset-x-0 bottom-4 z-40 flex justify-center px-4"
          >
            <div className="flex items-center gap-3 rounded-2xl border border-border-strong glass-strong px-4 py-3 shadow-xl">
              <div className="flex items-center gap-1.5 text-sm font-medium pr-2 border-r border-border">
                <CheckSquare className="size-4 text-primary" />
                {selectedIds.length} selected
              </div>
              <Button
                size="sm"
                variant="secondary"
                onClick={() => toast.success(`Added ${selectedIds.length} leads to list`)}
              >
                <ListPlus className="size-4" />
                Add to list
              </Button>
              <Button
                size="sm"
                variant="secondary"
                onClick={() => toast.success(`Exporting ${selectedIds.length} leads…`)}
              >
                <Download className="size-4" />
                Export selected
              </Button>
              <Button size="sm" variant="ghost" onClick={onClearSelection}>
                <X className="size-4" />
              </Button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
