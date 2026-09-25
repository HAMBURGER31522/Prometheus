// Design-token lint (PLAN 9.2 / D4): colors and font literals may only appear in
// src/shared/tokens.css, and tokens.css values must come from the approved palette.
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const srcRoot = fileURLToPath(new URL("../src", import.meta.url));
const tokensFile = join(srcRoot, "shared", "tokens.css");

const ALLOWED_HEX = new Set([
  "#fff",
  "#f2f5f7",
  "#414b55",
  "#242d35",
  "#65717d",
  "#c8562e",
  "#e9edf0",
  "#fff8e8",
]);
const ALLOWED_RGBA = "rgba(36,45,53,.08)";

const PATTERNS = [
  { name: "hex color", re: /#[0-9a-fA-F]{3,8}\b/g },
  { name: "rgb( literal", re: /\brgb\(/g },
  { name: "hsl( literal", re: /\bhsl\(/g },
  { name: "font-family literal", re: /font-family/g },
];

function listFiles(dir) {
  const out = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) out.push(...listFiles(full));
    else if (/\.(css|tsx?|mjs)$/.test(entry.name)) out.push(full);
  }
  return out;
}

const problems = [];

for (const file of listFiles(srcRoot)) {
  const text = readFileSync(file, "utf8");
  const isTokens = file === tokensFile;
  if (isTokens) {
    for (const hex of text.matchAll(/#[0-9a-fA-F]{3,8}\b/g)) {
      if (!ALLOWED_HEX.has(hex[0].toLowerCase())) {
        problems.push(`${file}: color ${hex[0]} is not in the PLAN 9.2 palette`);
      }
    }
    for (const rgba of text.matchAll(/rgba\([^)]*\)/g)) {
      if (rgba[0].replace(/\s+/g, "") !== ALLOWED_RGBA) {
        problems.push(`${file}: rgba value ${rgba[0]} is not the allowed ${ALLOWED_RGBA}`);
      }
    }
    continue;
  }
  for (const { name, re } of PATTERNS) {
    for (const match of text.matchAll(re)) {
      const upTo = text.slice(0, match.index);
      const line = upTo.split("\n").length;
      problems.push(`${file}:${line}: ${name} "${match[0]}" (only allowed in shared/tokens.css)`);
    }
  }
}

if (problems.length > 0) {
  for (const problem of problems) console.error(problem);
  console.error(`lint:design: ${problems.length} violation(s)`);
  process.exit(1);
}
console.log("lint:design: ok");
