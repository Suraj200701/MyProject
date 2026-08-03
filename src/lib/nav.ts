import {
  LayoutDashboard,
  Search,
  Map,
  MapPinned,
  Database,
  Plug,
  ScanLine,
  Download,
  LineChart,
  Settings,
  Users,
  CreditCard,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  title: string;
  href: string;
  icon: LucideIcon;
  badge?: string;
}

export interface NavSection {
  title: string;
  items: NavItem[];
}

export const navSections: NavSection[] = [
  {
    title: "Workspace",
    items: [
      { title: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
      { title: "Lead Search", href: "/dashboard/search", icon: Search },
      { title: "Map Search", href: "/dashboard/map", icon: Map },
      { title: "Google Maps Search", href: "/dashboard/google-maps", icon: MapPinned },
      { title: "Lead Database", href: "/dashboard/leads", icon: Database },
    ],
  },
  {
    title: "Intelligence",
    items: [
      { title: "Lead Intelligence", href: "/dashboard/intelligence", icon: LineChart },
      { title: "Website Scanner", href: "/dashboard/scanner", icon: ScanLine },
      { title: "Export Center", href: "/dashboard/export", icon: Download },
    ],
  },
  {
    title: "Platform",
    items: [
      { title: "API Manager", href: "/dashboard/api-manager", icon: Plug },
      { title: "Team", href: "/dashboard/team", icon: Users },
      { title: "Billing", href: "/dashboard/billing", icon: CreditCard },
      { title: "Settings", href: "/dashboard/settings", icon: Settings },
    ],
  },
];

export const allNavItems = navSections.flatMap((s) => s.items);
