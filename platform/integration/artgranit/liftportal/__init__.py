"""Модуль портала Artgranit: витрина платформы LiftPortal.

Контракт ядра (docs/CORE_MODULES.md исходного проекта):
  * имя blueprint обязано совпадать с ключом модуля — «liftportal»;
  * маршруты пишутся БЕЗ префикса, префикс /UNA.md/orasldev/liftportal подставляет ядро;
  * ядро на время импорта закрывает app.add_url_rule и app.register_blueprint — их здесь нет.

Данные модуль берёт по REST API платформы (X-API-Key), собственных Oracle-объектов не заводит,
поэтому инвариант «рабочие данные модуля — в Oracle» не нарушается: LiftPortal остаётся
системой-источником, а портал показывает её витрину.
"""
from flask import Blueprint

blueprint = Blueprint("liftportal", __name__, template_folder="templates")

from . import routes  # noqa: E402,F401
