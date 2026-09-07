import { SectionCard } from "@/components/ui/section-card";

/**
 * Settings section wrapper on the house SectionCard recipe. Passing `id`
 * adds scroll-mt-6 automatically (see section-card.tsx) so the scroll-spy
 * anchor lands below the sticky header.
 */
export function SettingsSection({
  id,
  title,
  description,
  children,
}: {
  id: string;
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <SectionCard id={id} title={title} description={description}>
      <div className="space-y-4">{children}</div>
    </SectionCard>
  );
}
