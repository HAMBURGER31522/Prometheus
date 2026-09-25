import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";

import App from "./App";

it("renders the app shell", () => {
  render(<App />);
  const heading = screen.getByRole("heading", { level: 1 });
  expect(heading.textContent).toBe("Prometheus");
});
