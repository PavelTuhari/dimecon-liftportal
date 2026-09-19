"""Проверка суммы прописью: согласование числительных и названий валют."""
import sys

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from portal.services.documents import amount_in_words  # noqa: E402

cases = [
    (62480.00, "MDL", "Шестьдесят две тысячи четыреста восемьдесят леев 00 бань"),
    (1.00, "MDL", "Один лей 00 бань"),
    (2.00, "MDL", "Два лея 00 бань"),
    (5.50, "MDL", "Пять леев 50 бань"),
    (21.01, "MDL", "Двадцать один лей 01 бан"),
    (102.02, "MDL", "Сто два лея 02 бана"),
    (1000.00, "MDL", "Одна тысяча леев 00 бань"),
    (2000.00, "MDL", "Две тысячи леев 00 бань"),
    (11000.00, "MDL", "Одиннадцать тысяч леев 00 бань"),
    (1234567.89, "MDL", "Один миллион двести тридцать четыре тысячи пятьсот шестьдесят семь леев 89 бань"),
    (0.00, "MDL", "Ноль леев 00 бань"),
    (100.00, "EUR", "Сто евро 00 центов"),
    (21.00, "USD", "Двадцать один доллар 00 центов"),
]
bad = 0
for value, cur, expect in cases:
    got = amount_in_words(value, cur)
    ok = got == expect
    bad += 0 if ok else 1
    print(f"  {'OK  ' if ok else 'ОШИБКА'} {value:>12,.2f} {cur} -> {got}")
    if not ok:
        print(f"         ожидалось: {expect}")
print(f"\nпройдено {len(cases) - bad} из {len(cases)}")
sys.exit(1 if bad else 0)
