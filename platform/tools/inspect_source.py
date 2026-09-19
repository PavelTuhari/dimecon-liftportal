"""Просмотр выгруженного содержимого dimecon.md перед переносом."""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
d = json.load(open("../docs/dimecon_source/content.json", encoding="utf-8"))

for tip in ("auto", "turn", "senile", "transport", "vinzari"):
    print("=" * 76)
    print(tip.upper())
    for lang in ("ru", "ro", "en"):
        rows = d["tips"][tip][lang]
        for i, r in enumerate(rows):
            print(f"[{lang}][{i}] {r['title'] or r['list_title']}")
            if r.get("summary"):
                print(f"        СВОДКА: {r['summary'][:220]}")
        print("   ---")

print("=" * 76)
print("SERVICII")
for i, r in enumerate(d["tips"]["servicii"]["ru"]):
    print(f"[{i}] {r['title'] or r['list_title']}")
    if r.get("summary"):
        print(f"      {r['summary'][:160]}")
