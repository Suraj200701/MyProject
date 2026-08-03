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
import { useLeads, useProviders, useSearchHistory } from "@/lib/api/queries";
import { useUiStore } from "@/store/ui-store";
import { Building2, History, Plug, ArrowRight } from "lucide-react";

/** Debounce so typing doesn't fire a request per keystroke. */
function useDebounced<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = React.useState(value);
  React.useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}

export function CommandPalette() {
  const { commandOpen, setCommandOpen } = useUiStore();
  const router = useRouter();
  const [term, setTerm] = React.useState("");
  const debouncedTerm = useDebounced(term, 250);

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

  // Everything is fetched only while the palette is open, and lead results are
  // searched server-side so the palette can reach the whole database rather
  // than filtering a page of it client-side.
  const { data: leadsPage } = useLeads(
    commandOpen ? { page_size: 5, search: debouncedTerm || undefined } : {},
  );
  const { data: searches } = useSearchHistory(commandOpen ? { page_size: 3 } : {});
  const { data: providers } = useProviders();

  const leads = commandOpen ? (leadsPage?.items ?? []) : [];
  const recentSearches = commandOpen ? (searches?.items ?? []) : [];
  const providerList = commandOpen ? (providers ?? []).slice(0, 3) : [];

  const go = (href: string) => {
    setCommandOpen(false);
    setTerm("");
    router.push(href);
  };

  return (
    <CommandDialog open={commandOpen} onOpenChange={setCommandOpen}>
      <CommandInput
        placeholder="Search leads, companies, providers, pages…"
        value={term}
        onValueChange={setTerm}
      />
      <CommandList>
        <CommandEmpty>No results found.</CommandEmpty>
        <CommandGroup heading="Navigate">
          {allNavItems.map((item) => (
            <CommandItem key={item.href} onSelect={() => go(item.href)}>
              <item.icon />
              <span>{item.title}</span>
              <CommandShortcut>
                <ArrowRight className="size-3" />
              </CommandShortcut>
            </CommandItem>
          ))}
        </CommandGroup>

        {leads.length > 0 && (
          <>
            <CommandSeparator />
            <CommandGroup heading="Leads">
              {leads.map((lead) => (
                <CommandItem
                  key={lead.id}
                  // cmdk filters on this value; without it the list would be
                  // re-filtered client-side against the server's own results.
                  value={`lead-${lead.id}-${lead.company}`}
                  onSelect={() => go(`/dashboard/leads/${lead.id}`)}
                >
                  <Building2 />
                  <span>{lead.company}</span>
                  <CommandShortcut>{lead.city}</CommandShortcut>
                </CommandItem>
              ))}
            </CommandGroup>
          </>
        )}

        {recentSearches.length > 0 && (
          <>
            <CommandSeparator />
            <CommandGroup heading="Recent Searches">
              {recentSearches.map((s) => (
                <CommandItem
                  key={s.id}
                  value={`search-${s.id}-${s.query}`}
                  onSelect={() => go("/dashboard/search")}
                >
                  <History />
                  <span>{s.query}</span>
                  <CommandShortcut>{s.results} results</CommandShortcut>
                </CommandItem>
              ))}
            </CommandGroup>
          </>
        )}

        {providerList.length > 0 && (
          <>
            <CommandSeparator />
            <CommandGroup heading="API Providers">
              {providerList.map((p) => (
                <CommandItem
                  key={p.id}
                  value={`provider-${p.id}-${p.name}`}
                  onSelect={() => go("/dashboard/api-manager")}
                >
                  <Plug />
                  <span>{p.name}</span>
                </CommandItem>
              ))}
            </CommandGroup>
          </>
        )}
      </CommandList>
    </CommandDialog>
  );
}
