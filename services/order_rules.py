"""Минимальный заказ у поставщика: сумма количеств всех его позиций в одной заявке."""
import html

# напитки (кола, тоник, вода, соки) — от 5 уп., кофе и чай — от 2, пиво — от 1, остальные — от 6
DEFAULT_MIN = 6
SUPPLIER_MIN = {
    "мултон": 5,       # Rich: кола, тоник, соки, Bona aqua
    "бригантина": 5,   # вода Мевер, Ричал-су
    "денис": 2,        # кофе, какао, сахар, фильтры
    "стас": 2,         # чай
    "майкл": 2,        # матча
    "премиум": 4,      # гранатовый сок Il Primo; пиво у Премиума не берём
    # пиво — от 1
    "сочи пиво": 1,
    "кп пиво": 1,
    "драфт": 1,
    "хорос": 1,
    "виталя": 1,
}


def _key(supplier: str) -> str:
    return " ".join((supplier or "").split()).lower()


def min_for(supplier: str) -> int:
    return SUPPLIER_MIN.get(_key(supplier), DEFAULT_MIN)


def shortfalls(rows) -> list[tuple[str, int, int]]:
    """rows: [(supplier, quantity), ...] из корзины → [(поставщик, набрано, минимум)] где не хватает."""
    totals, names = {}, {}
    for supplier, qty in rows:
        if not supplier:
            continue  # без поставщика — не к кому применять минимум
        k = _key(supplier)
        totals[k] = totals.get(k, 0) + (qty or 0)
        names.setdefault(k, " ".join(supplier.split()))
    return [(names[k], total, min_for(names[k])) for k, total in totals.items() if total < min_for(names[k])]


def shortfall_text(short: list[tuple[str, int, int]]) -> str:
    lines = [f"▪️ <b>{html.escape(name)}</b>: {got} из {need} шт. — добавьте ещё {need - got}" for name, got, need in short]
    return (
        "⚠️ <b>Не набран минимальный заказ у поставщика</b>\n\n" + "\n".join(lines) +
        "\n\nДобавьте товаров этого поставщика или уберите его позиции из корзины.\n"
        "<i>Минимум: напитки — от 5 уп., кофе и чай — от 2, пиво — от 1, остальное — от 6 (сумма по поставщику).</i>"
    )
