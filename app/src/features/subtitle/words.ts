// Hover lookup (PLAN 15.4.9): which words of a subtitle line can be looked up, and where the
// five online dictionaries show a word.

export type Token = { text: string; word?: string };

export function tokenize(text: string): Token[] {
  return [{ text }];
}

export function isForeign(_text: string): boolean {
  return false;
}

export const DICTIONARIES: { name: string; url: (word: string) => string }[] = [];
