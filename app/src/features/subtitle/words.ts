// Hover lookup (PLAN 15.4.9, 15.4.10): which words of a subtitle line can be looked up, and where
// the seven online dictionaries show a word.

export type Token = { text: string; word?: string };

const WORD = /[A-Za-z]+(?:['’-][A-Za-z]+)*/g;

/** Words and the text between them; joining every token's text gives the line back. */
export function tokenize(text: string): Token[] {
  const tokens: Token[] = [];
  let last = 0;
  for (const match of text.matchAll(WORD)) {
    if (match.index > last) tokens.push({ text: text.slice(last, match.index) });
    tokens.push({ text: match[0], word: match[0] });
    last = match.index + match[0].length;
  }
  if (last < text.length) tokens.push({ text: text.slice(last) });
  return tokens;
}

/** A line worth looking words up in: at least half of its letters are Latin. */
export function isForeign(text: string): boolean {
  const letters = [...text].filter((char) => /\p{L}/u.test(char));
  const latin = letters.filter((char) => /[A-Za-z]/.test(char));
  return letters.length > 0 && latin.length * 2 >= letters.length;
}

const q = encodeURIComponent;

export const DICTIONARIES: { name: string; url: (word: string) => string }[] = [
  { name: "有道", url: (word) => `https://www.youdao.com/result?word=${q(word)}&lang=en` },
  { name: "剑桥", url: (word) => `https://dictionary.cambridge.org/dictionary/english-chinese-simplified/${q(word.toLowerCase())}` },
  { name: "柯林斯", url: (word) => `https://www.collinsdictionary.com/dictionary/english/${q(word.toLowerCase())}` },
  { name: "必应", url: (word) => `https://cn.bing.com/dict/search?q=${q(word)}` },
  { name: "韦氏", url: (word) => `https://www.merriam-webster.com/dictionary/${q(word)}` },
  // Oxford's search lands on the entry (also for Sitting, well-known); /dicts/en/<word> is Eudic's own link.
  { name: "牛津", url: (word) => `https://www.oxfordlearnersdictionaries.com/search/english/?q=${q(word)}` },
  { name: "欧路", url: (word) => `https://dict.eudic.net/dicts/en/${q(word)}` },
];
