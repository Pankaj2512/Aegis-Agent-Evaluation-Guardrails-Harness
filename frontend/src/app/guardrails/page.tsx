"use client";

import { GuardrailPlayground } from "@/components/guardrails/GuardrailPlayground";
import { GettingStartedBanner } from "@/components/onboarding/GettingStartedBanner";
import { PageHeader } from "@/components/ui/page-header";
import { PageEnter } from "@/components/motion";

export default function GuardrailsPage() {
  return (
    <PageEnter className="page-container space-y-6">
      <PageHeader
        title="Guardrails"
        description="Stress-test policies before adding guardrail nodes on the canvas."
      />
      <GettingStartedBanner
        onboardingKey="guardrails"
        title="Catch unsafe output before it ships"
        description="Draft a policy here, watch it block or mask a sample, then drop a guardrail node onto a workflow to enforce it in production."
        primaryHref="/templates?filter=guardrail"
        primaryLabel="Start from a guardrail template"
      />
      <GuardrailPlayground />
    </PageEnter>
  );
}
