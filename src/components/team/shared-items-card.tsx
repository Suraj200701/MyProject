import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { AsyncContent } from "@/components/shared/async-content";
import type { WorkspaceItem } from "@/components/team/types";

/**
 * A short list of workspace-wide resources (leads, searches).
 *
 * Previously each row claimed "Shared by <person>". The API exposes no
 * per-resource owner, so that name was fabricated; the row now shows the
 * provenance the backend does report — a lead's source provider, a search's
 * location and result count. Markup and styling are unchanged.
 */
export function SharedItemsCard({
  title,
  items,
  isPending = false,
  isError = false,
  error,
  emptyMessage,
}: {
  title: string;
  items: WorkspaceItem[];
  isPending?: boolean;
  isError?: boolean;
  error?: unknown;
  emptyMessage?: string;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <AsyncContent
        isPending={isPending}
        isError={isError}
        error={error}
        isEmpty={items.length === 0}
        emptyMessage={emptyMessage ?? "Nothing here yet."}
        className="min-h-[96px] p-5"
      >
        <CardContent className="space-y-1">
          {items.map((item) => (
            <div key={item.id} className="flex items-center gap-3 py-2">
              <Avatar className="size-7 border border-border">
                <AvatarFallback className="bg-surface-2 text-[10px]">{item.initials}</AvatarFallback>
              </Avatar>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">{item.name}</p>
                <p className="truncate text-xs text-muted-foreground">{item.meta}</p>
              </div>
            </div>
          ))}
        </CardContent>
      </AsyncContent>
    </Card>
  );
}
