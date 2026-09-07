"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import { Keyboard, Moon, Plus, Search, Shield, Sun } from "lucide-react";
import { openCommandPalette } from "@/components/layout/CommandPalette";
import { isActivePath, navItems } from "@/components/layout/nav-items";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useTheme } from "@/providers/ThemeProvider";
import { cn } from "@/lib/utils";

interface AppRailProps {
  onOpenShortcutsHelp?: () => void;
}

export function AppRail({ onOpenShortcutsHelp }: AppRailProps) {
  const pathname = usePathname();
  const { toggleTheme } = useTheme();

  return (
    <nav
      aria-label="Primary"
      className="fixed inset-y-0 left-0 z-40 flex w-14 flex-col items-center border-r border-border bg-surface-elevated py-3"
    >
      <Tooltip>
        <TooltipTrigger asChild>
          <Link
            href="/"
            aria-label="Aegis home"
            className="focus-ring group flex h-8 w-8 items-center justify-center rounded-lg border border-border bg-surface-elevated transition-colors hover:border-border-strong"
          >
            <Shield className="h-4 w-4 text-foreground" strokeWidth={2} />
          </Link>
        </TooltipTrigger>
        <TooltipContent side="right">Aegis home</TooltipContent>
      </Tooltip>

      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            asChild
            size="icon"
            className="focus-ring mt-3 h-10 w-10"
            aria-label="New workflow"
          >
            <Link href="/workflows/new">
              <Plus className="h-[18px] w-[18px]" />
            </Link>
          </Button>
        </TooltipTrigger>
        <TooltipContent side="right">New workflow</TooltipContent>
      </Tooltip>

      <div className="my-3 w-8 border-b border-border" />

      <div className="flex flex-col items-center gap-1">
        {navItems.map(({ href, label, exact, icon: Icon }) => {
          const active = isActivePath(pathname, href, exact);
          return (
            <Tooltip key={href}>
              <TooltipTrigger asChild>
                <Link
                  href={href}
                  aria-label={label}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "focus-ring relative flex h-10 w-10 items-center justify-center rounded-md border border-transparent transition-colors",
                    active
                      ? "nav-link-active"
                      : "text-muted hover:bg-surface-hover hover:text-foreground"
                  )}
                >
                  <Icon className="h-[18px] w-[18px]" />
                  {active && (
                    <motion.span
                      layoutId="nav-active-rail"
                      className="absolute -left-px inset-y-2 w-0.5 rounded-r-full bg-foreground"
                    />
                  )}
                </Link>
              </TooltipTrigger>
              <TooltipContent side="right">{label}</TooltipContent>
            </Tooltip>
          );
        })}
      </div>

      <div className="mt-auto flex flex-col items-center gap-1">
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="focus-ring h-10 w-10 text-muted"
              onClick={openCommandPalette}
              aria-label="Search"
            >
              <Search className="h-[18px] w-[18px]" />
            </Button>
          </TooltipTrigger>
          <TooltipContent side="right">Search ⌘K</TooltipContent>
        </Tooltip>

        {onOpenShortcutsHelp && (
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="focus-ring h-10 w-10 text-muted"
                onClick={onOpenShortcutsHelp}
                aria-label="Keyboard shortcuts"
              >
                <Keyboard className="h-[18px] w-[18px]" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="right">Keyboard shortcuts</TooltipContent>
          </Tooltip>
        )}

        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="focus-ring h-10 w-10 text-muted"
              onClick={toggleTheme}
              aria-label="Toggle theme"
            >
              {/* Both icons in the markup, CSS picks one: the theme class is
                  applied pre-hydration, so server and client HTML must match. */}
              <Sun className="hidden h-[18px] w-[18px] dark:block" />
              <Moon className="h-[18px] w-[18px] dark:hidden" />
            </Button>
          </TooltipTrigger>
          <TooltipContent side="right">Toggle theme</TooltipContent>
        </Tooltip>
      </div>
    </nav>
  );
}
