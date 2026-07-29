import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";

const MEMBER_INITIALS = ["SG", "PM", "AK", "RN", "DV"];

export function TeamLiteSection() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Team</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center gap-3">
          <div className="flex -space-x-2">
            {MEMBER_INITIALS.map((initials) => (
              <Avatar key={initials} className="size-8 border-2 border-background">
                <AvatarFallback className="bg-surface-2 text-[11px]">{initials}</AvatarFallback>
              </Avatar>
            ))}
          </div>
          <p className="text-sm text-muted-foreground">{MEMBER_INITIALS.length} members in your workspace</p>
        </div>
        <Button asChild size="sm" variant="secondary">
          <Link href="/dashboard/team">Manage Team</Link>
        </Button>
      </CardContent>
    </Card>
  );
}
