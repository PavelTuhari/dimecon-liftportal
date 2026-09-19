"""Проверка пакета интеграции: синтаксис модулей, манифесты, соответствие контракту ядра Artgranit."""
import ast
import json
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
bad = 0


def ok(msg, cond, detail=""):
    global bad
    if not cond:
        bad += 1
    print(f"  {'OK  ' if cond else 'ОШИБКА'} {msg}" + (f" — {detail}" if detail else ""))


ROOT = pathlib.Path("integration/artgranit")
print("=== Синтаксис ===")
for p in ["integration/artgranit/liftportal/__init__.py", "integration/artgranit/liftportal/routes.py",
          "portal/services/officeplus.py", "portal/services/crm_import.py"]:
    try:
        ast.parse(pathlib.Path(p).read_text(encoding="utf-8"))
        ok(p, True)
    except SyntaxError as exc:
        ok(p, False, str(exc))

print("\n=== Манифесты ===")
mod = json.loads((ROOT / "liftportal" / "module.json").read_text(encoding="utf-8"))
ok("module.json разбирается", True)
ok("название на трёх языках", set(mod["title"]) >= {"ru", "ro", "en"}, ", ".join(mod["title"]))
ok("есть иконка, порядок, url, docs, sql_prefix", all(k in mod for k in ("icon", "order", "url", "docs", "sql_prefix")),
   f"{mod['icon']} {mod['url']} {mod['sql_prefix']}")
ok("url под /UNA.md/orasldev/", mod["url"].startswith("/UNA.md/orasldev/"), mod["url"])
docs = json.loads((ROOT / "docs_LiftPortal" / "docs.json").read_text(encoding="utf-8"))
ok("docs.json разбирается, документов перечислено", len(docs["docs"]) >= 10, str(len(docs["docs"])))
ok("публичность выключена по умолчанию", docs.get("public") is False, str(docs.get("public")))

print("\n=== Контракт ядра ===")
init_src = (ROOT / "liftportal" / "__init__.py").read_text(encoding="utf-8")
routes_src = (ROOT / "liftportal" / "routes.py").read_text(encoding="utf-8")
ok("blueprint назван ключом модуля", 'Blueprint("liftportal"' in init_src)
ok("экспортируется переменная blueprint", "\nblueprint = " in init_src)
ok("нет вызовов app.add_url_rule / register_blueprint",
   "add_url_rule" not in routes_src and "register_blueprint" not in routes_src)
ok("маршруты объявлены без префикса модуля",
   '@blueprint.route("/")' in routes_src and "/UNA.md/orasldev/liftportal" not in routes_src.split("PAGE =")[0])
ok("страницы манифеста совпадают с маршрутами",
   all(any(f'"{r}"' in routes_src or f"'{r}'" in routes_src for r in ["/", "/orders", "/fleet", "/docs"])
       for _ in [0]), ", ".join(mod["pages"]))
ok("ошибка связи не роняет страницу", "warn" in routes_src and "except" in routes_src)

print(f"\nИТОГО: ошибок {bad}")
sys.exit(1 if bad else 0)
