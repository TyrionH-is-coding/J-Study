import Link from "next/link";
import type { ReactNode } from "react";

const navigation = [
  { href: "/modes", label: "Modes" },
  { href: "/login", label: "Login" },
  { href: "/register", label: "Register" },
];

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="app-shell">
      <header className="site-header">
        <Link className="brand" href="/">
          J-Study
        </Link>
        <span className="product-state">Learning workspace foundation</span>
        <nav aria-label="Primary navigation">
          {navigation.map((item) => (
            <Link href={item.href} key={item.href}>
              {item.label}
            </Link>
          ))}
        </nav>
      </header>
      <main>{children}</main>
    </div>
  );
}
