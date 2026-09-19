"""Экспорт схемы в MySQL DDL: python tools/export_ddl.py > schema_mysql.sql"""
import sys
sys.path.insert(0, ".")
from portal.db import mysql_ddl  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
print("-- LiftPortal: схема для MySQL 8 (utf8mb4). Создаётся автоматически и при первом запуске приложения.")
print("-- CREATE DATABASE liftportal CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;\n")
print(mysql_ddl())
