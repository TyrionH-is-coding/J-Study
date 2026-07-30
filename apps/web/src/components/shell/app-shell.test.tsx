import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { renderWithProviders } from "@/test/render";
import { AppShell } from "./app-shell";
import { FeaturePlaceholder } from "./feature-placeholder";

describe("frontend foundation shell", () => {
  it("renders the multi-discipline brand and primary navigation", () => {
    renderWithProviders(
      <AppShell>
        <p>Content</p>
      </AppShell>,
    );

    expect(screen.getByRole("link", { name: "J-Study" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "Modes" })).toHaveAttribute("href", "/modes");
    expect(screen.getByText("Learning workspace foundation")).toBeInTheDocument();
  });

  it("renders an explicit non-interactive feature state", () => {
    renderWithProviders(
      <FeaturePlaceholder
        eyebrow="Account"
        title="Login"
        description="Authentication is outside the foundation rebuild."
      />,
    );

    expect(screen.getByRole("heading", { name: "Login" })).toBeInTheDocument();
    expect(screen.queryByRole("form")).not.toBeInTheDocument();
    expect(screen.getByText("Foundation ready")).toBeInTheDocument();
  });
});
