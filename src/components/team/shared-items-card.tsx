import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import type { SharedItem } from "@/components/team/types";

export function SharedItemsCard({ title, items }: { title: string; items: SharedItem[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-1">
        {items.map((item) => (
          <div key={item.id} className="flex items-center gap-3 py-2">
            <Avatar className="size-7 border border-border">
              <AvatarFallback className="bg-surface-2 text-[10px]">{item.sharedByInitials}</AvatarFallback>
            </Avatar>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium">{item.name}</p>
              <p className="text-xs text-muted-foreground">
                Shared by {item.sharedBy} · {item.sharedAt}
              </p>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
