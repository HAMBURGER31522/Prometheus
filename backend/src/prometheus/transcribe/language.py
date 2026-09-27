"""A transcript's language from its text, for engines that report none (PLAN 15.4.9): 必剪
recognises Chinese and English but only returns text, and a custom endpoint may omit it."""


def guess_language(texts) -> str:
    """"zh" when Han characters outnumber Latin letters, "en" when Latin letters do, else ""."""
    han = latin = 0
    for text in texts:
        for char in text:
            if "一" <= char <= "鿿":
                han += 1
            elif char.isascii() and char.isalpha():
                latin += 1
    if not han and not latin:
        return ""
    return "zh" if han >= latin else "en"
