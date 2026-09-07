"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Sparkles, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { dismissOnboarding, isOnboardingDismissed, type OnboardingKey } from "@/lib/onboarding";

interface GettingStartedBannerProps {
  onboardingKey: OnboardingKey;
  title: string;
  description: string;
  primaryHref: string;
  primaryLabel: string;
  secondaryHref?: string;
  secondaryLabel?: string;
}

export function GettingStartedBanner({
  onboardingKey,
  title,
  description,
  primaryHref,
  primaryLabel,
  secondaryHref,
  secondaryLabel,
}: GettingStartedBannerProps) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    setVisible(!isOnboardingDismissed(onboardingKey));
  }, [onboardingKey]);

  if (!visible) return null;

  const handleDismiss = () => {
    dismissOnboarding(onboardingKey);
    setVisible(false);
  };

  return (
    <div className="rounded-lg border border-border bg-surface p-4 shadow-elev-1 sm:p-5">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border bg-surface-input text-muted">
            <Sparkles className="h-4 w-4" />
          </div>
          <div>
            <p className="font-medium text-foreground">{title}</p>
            <p className="mt-1 max-w-xl text-sm text-muted">{description}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <Button asChild size="sm">
                <Link href={primaryHref}>{primaryLabel}</Link>
              </Button>
              {secondaryHref && secondaryLabel && (
                <Button asChild size="sm" variant="outline">
                  <Link href={secondaryHref}>{secondaryLabel}</Link>
                </Button>
              )}
            </div>
          </div>
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="shrink-0 self-start"
          onClick={handleDismiss}
          aria-label="Dismiss getting started banner"
        >
          <X className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
