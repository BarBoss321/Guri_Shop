import re
from difflib import SequenceMatcher

# Кириллица → латиница: «джеймсон» и «Jameson» сводятся к похожему виду
# и находятся нечётким сравнением
_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ж": "zh", "з": "z",
    "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p",
    "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "c", "ч": "ch",
    "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}
FUZZY_THRESHOLD = 0.8


def _words(text: str) -> list[str]:
    # SQLite LOWER() не умеет кириллицу, поэтому всё сравнение — здесь, в Python
    text = text.lower().replace("ё", "е")
    return re.findall(r"\w+", text)


def _stem(word: str) -> str:
    # отрезаем окончание: «самбуку» → «самбу», «соки» → «сок»
    return word if len(word) <= 4 else word[:max(4, len(word) - 2)]


def _latin(word: str) -> str:
    word = word.replace("дж", "j")
    word = "".join(_TRANSLIT.get(ch, ch) for ch in word)
    # одинаково звучащие латинские буквы: courvoisier ≈ курвуазье
    for a, b in (("ph", "f"), ("x", "ks"), ("c", "k"), ("q", "k"), ("w", "v"), ("z", "s")):
        word = word.replace(a, b)
    return word


def _consonants(word: str) -> str:
    # «джеймсон» и «jameson» по гласным расходятся, а согласные совпадают: jmsn
    return re.sub(r"[aeiouy]", "", word)


def _similarity(q: str, w: str) -> float:
    score = SequenceMatcher(None, q, w).ratio()
    qc, wc = _consonants(q), _consonants(w)
    if len(qc) >= 4 and len(wc) >= 4:
        score = max(score, SequenceMatcher(None, qc, wc).ratio())
    return score


def _exact_match(query: list[str], name: list[str]) -> bool:
    # каждое слово запроса должно найтись в названии (по началу слова или внутри)
    return all(any(_stem(q) in w for w in name) for q in query)


def _fuzzy_score(query: list[str], name: list[str]) -> float:
    if not name:
        return 0.0
    latin_name = [_latin(w) for w in name]
    scores = [
        max(_similarity(_latin(q), w) for w in latin_name)
        for q in query
    ]
    return sum(scores) / len(scores)


def search_items(items: list[tuple], query: str) -> tuple[list[tuple], bool]:
    """
    items: [(id, name, category_text, ...)] — category_text: названия категорий товара,
    чтобы «вино» находило вина, даже если в названии слова «вино» нет.
    Возвращает (найденное, точно ли): сначала точные совпадения, если их нет — с опечатками.
    """
    q = _words(query)
    if not q:
        return [], True

    prepared = [(item, _words(item[1] or ""), _words(f"{item[1]} {item[2] or ''}")) for item in items]
    exact = [item for item, _, words in prepared if _exact_match(q, words)]
    if exact:
        return sorted(exact, key=lambda it: it[1].lower()), True

    # опечатки ищем только по названию: категории дают слишком много ложных совпадений
    scored = [(item, _fuzzy_score(q, name)) for item, name, _ in prepared]
    scored = [s for s in scored if s[1] >= FUZZY_THRESHOLD]
    scored.sort(key=lambda s: s[1], reverse=True)
    return [item for item, _ in scored], False
