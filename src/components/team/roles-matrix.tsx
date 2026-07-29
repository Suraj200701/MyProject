import { Check, X } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PERMISSION_KEYS, ROLE_PERMISSIONS } from "@/components/team/mock-data";

const ROLES = ["Owner", "Admin", "Member", "Viewer"];

export function RolesMatrix() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Roles &amp; Permissions</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted-foreground">
                <th className="py-2 pr-3 font-medium">Permission</th>
                {ROLES.map((r) => (
                  <th key={r} className="px-2 py-2 text-center font-medium">
                    {r}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {PERMISSION_KEYS.map((perm) => (
                <tr key={perm} className="border-b border-border/60 last:border-0">
                  <td className="py-2.5 pr-3 text-foreground">{perm}</td>
                  {ROLES.map((role) => (
                    <td key={role} className="px-2 py-2.5 text-center">
                      {ROLE_PERMISSIONS[role][perm] ? (
                        <Check className="mx-auto size-4 text-success" />
                      ) : (
                        <X className="mx-auto size-4 text-muted-foreground/40" />
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}
