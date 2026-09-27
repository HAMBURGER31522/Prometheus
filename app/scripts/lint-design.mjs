// Design lint (PLAN 15.4.5): colours and font families live only in src/shared/tokens.css,
// easing curves and durations only in src/shared/motion.css. Everything else refers to them
// through var(--…). Run: npm run lint:design
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const srcRoot = fileURLToPath(new URL("../src", import.meta.url));
const tokensFile = join(srcRoot, "shared", "tokens.css");
const motionFile = join(srcRoot, "shared", "motion.css");

const COLOR_RULES = [
  { name: "hex colour", re: /#[0-9a-fA-F]{3,8}\b/g },
  { name: "rgb()/rgba() colour", re: /\brgba?\(/g },
  { name: "hsl() colour", re: /\bhsla?\(/g },
  { name: "font-family literal", re: /font-family\s*:(?!\s*var\()/g },
];
const MOTION_RULES = [
  { name: "easing curve", re: /\bcubic-bezier\(|\blinear\(|(?<!-)\bease(?:-in-out|-in|-out)?\b(?!-)/g },
  { name: "literal duration", re: /(?:transition|animation)[^;{}]*?\b\d*\.?\d+m?s\b/g },
];

function listFiles(dir) {
  const out = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) out.push(...listFiles(full));
    else if (/\.(css|tsx?)$/.test(entry.name) && !/\.test\.tsx?$/.test(entry.name)) out.push(full);
  }
  return out;
}

const problems = [];
for (const file of listFiles(srcRoot)) {
  const text = readFileSync(file, "utf8");
  const rules = [...(file === tokensFile ? [] : COLOR_RULES), ...(file === motionFile ? [] : MOTION_RULES)];
  for (const { name, re } of rules) {
    for (const match of text.matchAll(re)) {
      const line = text.slice(0, match.index).split("\n").length;
      problems.push(`${file}:${line}: ${name} "${match[0].trim()}"`);
    }
  }
}

if (problems.length > 0) {
  for (const problem of problems) console.error(problem);
  console.error(`lint:design: ${problems.length} violation(s): colours belong in shared/tokens.css, curves in shared/motion.css`);
  process.exit(1);
}
console.log("lint:design: ok");
