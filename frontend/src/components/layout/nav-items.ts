import {
  BarChart3,
  LayoutTemplate,
  Settings,
  Shield,
  Workflow,
  type LucideIcon,
} from "lucide-react";

export type NavItem = {
  href: string;
  label: string;
  exact?: boolean;
  icon: LucideIcon;
};

export const navItems: NavItem[] = [
  { href: "/", label: "Workflows", exact: true, icon: Workflow },
  { href: "/templates", label: "Templates", icon: LayoutTemplate },
  { href: "/observability", label: "Observability", icon: BarChart3 },
  { href: "/guardrails", label: "Guardrails", icon: Shield },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function isActivePath(pathname: string, href: string, exact?: boolean) {
  if (exact) {
    // Workflows is home; keep it active on workflow subroutes too.
    // Templates owns its own active state via the /templates nav item.
    return pathname === href || pathname.startsWith("/workflows");
  }
  // Run detail pages (/runs/*) belong to Observability.
  if (href === "/observability" && pathname.startsWith("/runs")) {
    return true;
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}
