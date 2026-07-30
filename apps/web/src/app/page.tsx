import Link from "next/link";

const routes = [
  ["/login", "Login"],
  ["/register", "Register"],
  ["/modes", "Learning modes"],
  ["/modes/course-outline", "Course outline"],
  ["/jobs/example-job", "Job workspace"],
] as const;

export default function HomePage() {
  return (
    <section className="overview" aria-labelledby="overview-title">
      <p className="eyebrow">J-Study web</p>
      <h1 id="overview-title">Frontend foundation is ready.</h1>
      <p>
        Routing, shared providers, the future API boundary, and automated verification are
        available. Product workflows and final visual rules remain intentionally separate.
      </p>
      <ul className="route-list">
        {routes.map(([href, label]) => (
          <li key={href}>
            <Link href={href}>{label}</Link>
            <code>{href}</code>
          </li>
        ))}
      </ul>
    </section>
  );
}
