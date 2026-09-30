// 「获取模型列表」 (PLAN 15.4.8): what to say when the endpoint answers with no models at all; some
// relays do not serve the list (user 2026-09-30), and the model's name can always be typed.
export function listNote(models: string[]): string {
  return models.length ? "" : "接口没有返回任何模型（有的中转不提供模型列表），可以直接填写模型名。";
}
