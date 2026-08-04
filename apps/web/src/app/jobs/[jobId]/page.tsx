import { FeaturePlaceholder } from "@/components/shell/feature-placeholder";

type JobPageProps = {
  params: Promise<{ jobId: string }>;
};

export default async function JobPage({ params }: JobPageProps) {
  const { jobId } = await params;
  return (
    <FeaturePlaceholder
      eyebrow="Job workspace"
      title={`Job ${jobId}`}
      description="Polling, generated material, sources, and exports are outside this foundation rebuild."
      detail="The dynamic route preserves the identifier without treating it as loaded job data."
    />
  );
}
