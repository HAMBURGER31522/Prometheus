import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";

import App from "./App";

it("renders the app shell", async () => {
  render(<App />);
  // App resolves the data-dir gate before rendering the shell heading.
  const heading = await screen.findByRole("heading", { level: 1 });
  expect(heading.textContent).toBe("Prometheus");
  expect(
    screen.getByText("选择一个数据目录，报告、导图与字幕都会存放在这里。"),
  ).toBeTruthy();
});
