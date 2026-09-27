// Whether a model accepts images, from the bundled models.dev snapshot (PLAN 15.4.8):
// true / false when models.dev knows the model, null when the user has to say.
import snapshot from "./model-vision.json";

const vision = new Set<string>(snapshot.vision);
const text = new Set<string>(snapshot.text);

export function visionOf(model: string): boolean | null {
  const id = model.trim().split("/").pop()?.toLowerCase() ?? "";
  if (vision.has(id)) return true;
  if (text.has(id)) return false;
  return null;
}
