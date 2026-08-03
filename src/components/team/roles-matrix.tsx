"use client";

import * as React from "react";
import { Check, X } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AsyncContent } from "@/components/shared/async-content";
import { usePermissionCatalogue, useRolePermissions } from "@/lib/api/queries";
import { roleLabel } from "@/components/team/adapters";

/**
 * Renders the role -> permission matrix the API actually enforces.
 *
 * Previously this table was a hardcoded copy of the backend's seed data, so it
 * would keep claiming a role had a capability after the seed changed. It now
 * reads `GET /team/roles` and `GET /team/permissions`, which are projections of
 * the same `role_permissions` rows `require_permission` checks against.
 */
export function RolesMatrix() {
  const roles = useRolePermissions();
  const catalogue = usePermissionCatalogue();

  const rows = React.useMemo(
    () =>
      (catalogue.data ?? []).map((permission) => ({
        code: permission.code,
        // Fall back to the code so an unseeded description shows something
        // meaningful rather than a blank row.
        label: permission.description || permission.code,
      })),
    [catalogue.data],
  );

  const columns = React.useMemo(
    () =>
      (roles.data ?? []).map((entry) => ({
        label: roleLabel(entry.role),
        granted: new Set(entry.permissions),
      })),
    [roles.data],
  );

  const isPending = roles.isPending || catalogue.isPending;
  const isError = roles.isError || catalogue.isError;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Roles &amp; Permissions</CardTitle>
      </CardHeader>
      <AsyncContent
        isPending={isPending}
        isError={isError}
        error={roles.error ?? catalogue.error}
        isEmpty={rows.length === 0 || columns.length === 0}
        emptyMessage="No roles configured."
        className="min-h-[180px] p-5"
      >
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-muted-foreground">
                  <th className="py-2 pr-3 font-medium">Permission</th>
                  {columns.map((column) => (
                    <th key={column.label} className="px-2 py-2 text-center font-medium">
                      {column.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.code} className="border-b border-border/60 last:border-0">
                    <td className="py-2.5 pr-3 text-foreground">{row.label}</td>
                    {columns.map((column) => (
                      <td key={column.label} className="px-2 py-2.5 text-center">
                        {column.granted.has(row.code) ? (
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
      </AsyncContent>
    </Card>
  );
}
