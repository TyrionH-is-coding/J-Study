import Link from "next/link";

type FeaturePlaceholderProps = {
  eyebrow: string;
  title: string;
  description: string;
  detail?: string;
};

export function FeaturePlaceholder({
  eyebrow,
  title,
  description,
  detail = "The technical foundation is ready. Business behavior is intentionally not connected.",
}: FeaturePlaceholderProps) {
  return (
    <section className="placeholder" aria-labelledby="feature-title">
      <p className="eyebrow">{eyebrow}</p>
      <h1 id="feature-title">{title}</h1>
      <p>{description}</p>
      <div className="foundation-state">
        <strong>Foundation ready</strong>
        <span>{detail}</span>
      </div>
      <Link className="text-link" href="/">
        Return to foundation overview
      </Link>
    </section>
  );
}
