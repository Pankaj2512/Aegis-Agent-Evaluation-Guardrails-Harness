import { RunDetailView } from "@/components/runs/RunDetailView";

export default function RunPage({ params }: { params: { id: string } }) {
  return <RunDetailView runId={params.id} />;
}