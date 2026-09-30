// Whether a model accepts images, from the bundled models.dev snapshot (PLAN 15.4.8):
// true / false when models.dev knows the model, null when the user has to say.
import snapshot from "./model-vision.json";

const vision = new Set<string>(snapshot.vision);
const text = new Set<string>(snapshot.text);

export function visionOf(model: string): boolean | null {
  // 「claude-opus-4-8[1m]」: Claude Code's suffix for the 1M window, not part of the model's name
  const id = model.trim().replace(/\[1m\]$/i, "").split("/").pop()?.toLowerCase() ?? "";
  if (vision.has(id)) return true;
  if (text.has(id)) return false;
  return null;
}
