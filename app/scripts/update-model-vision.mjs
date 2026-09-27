// Refresh the models.dev snapshot the settings page uses to prefill 「能看图」 (PLAN 15.4.8).
//   node scripts/update-model-vision.mjs
// Keeps only the last path segment of each model id (lower-case) and whether it accepts images,
// so the app never has to ask the user's endpoint (relays ban accounts that get probed).
import { writeFileSync } from "node:fs";

const response = await fetch("https://models.dev/api.json");
if (!response.ok) throw new Error(`models.dev ${response.status}`);
const catalogue = await response.json();
const vision = new Set();
const text = new Set();
for (const provider of Object.values(catalogue)) {
  for (const [key, model] of Object.entries(provider.models ?? {})) {
    const id = String(model.id ?? key).split("/").pop().toLowerCase();
    const inputs = model.modalities?.input ?? [];
    if (inputs.includes("image")) vision.add(id);
    else if (inputs.length) text.add(id);
  }
}
for (const id of vision) text.delete(id);
const snapshot = { source: "https://models.dev/api.json", date: new Date().toISOString().slice(0, 10), vision: [...vision].sort(), text: [...text].sort() };
writeFileSync(new URL("../src/features/settings/model-vision.json", import.meta.url), JSON.stringify(snapshot) + "\n");
console.log(`vision ${vision.size}, text-only ${text.size}`);
