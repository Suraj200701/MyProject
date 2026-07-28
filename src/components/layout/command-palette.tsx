"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
  CommandShortcut,
} from "@/components/ui/command";
import { allNavItems } from "@/lib/nav";
import { mockLeads, searchHistory, apiProviders } from "@/lib/mock-data";
import { useUiStore } from "@/store/ui-store";
import { Building2, History, Plug, ArrowRight } from "lucide-react";

export function CommandPalette() {
  const { commandOpen, setCommandOpen } = useUiStore();
  const router = useRouter();

  React.useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setCommandOpen(!commandOpen);
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [commandOpen, setCommandOpen]);

  const go = (href: string) => {
    setCommandOpen(false);
    router.push(href);
  };

  return (
    <CommandDialog open={commandOpen} onOpenChange={setCommandOpen}>
      <CommandInput placeholder="Search leads, companies, providers, pages…" />
      <CommandList>
        <CommandEmpty>No results found.</CommandEmpty>
        <CommandGroup heading="Navigate">
          {allNavItems.map((item) => (
            <CommandItem key={item.href} onSelect={() => go(item.href)}>
              <item.icon />
              <span>{item.title}</span>
              <CommandShortcut><ArrowRight className="size-3" /></CommandShortcut>
            </CommandItem>
          ))}
        </CommandGroup>
        <CommandSeparator />
        <CommandGroup heading="Leads">
          {mockLeads.slice(0, 5).map((lead) => (
            <CommandItem key={lead.id} onSelect={() => go(`/dashboard/leads/${lead.id}`)}>
              <Building2 />
              <span>{lead.company}</span>
              <CommandShortcut>{lead.city}</CommandShortcut>
            </CommandItem>
          ))}
        </CommandGroup>
        <CommandSeparator />
        <CommandGroup heading="Recent Searches">
          {searchHistory.slice(0, 3).map((s) => (
            <CommandItem key={s.id} onSelect={() => go("/dashboard/search")}>
              <History />
              <span>{s.query}</span>
            </CommandItem>
          ))}
        </CommandGroup>
        <CommandSeparator />
        <CommandGroup heading="API Providers">
          {apiProviders.slice(0, 3).map((p) => (
            <CommandItem key={p.id} onSelect={() => go("/dashboard/api-manager")}>
              <Plug />
              <span>{p.name}</span>
            </CommandItem>
          ))}
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}
