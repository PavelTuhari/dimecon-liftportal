"""Документооборот: рабочие пространства, теги, версии, запросы файлов, правила обработки.

Файл хранится как запись Media (локальный диск, ссылка или S3 — как настроено у компании).
Здесь добавляется то, ради чего заводят документооборот: где лежит, к чему относится,
какая версия актуальна, кто должен прислать недостающий документ и что делать автоматически.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import func, or_

from ..db import SessionLocal as db
from ..models import DocFolder, DocRequest, DocRule, Media, Task, Tenant

ACCESS_NAMES = {"internal": "Только сотрудники", "partner": "Сотрудники и партнёры", "link": "По ссылке"}
DEFAULT_FOLDERS = [("Договоры", "internal"), ("Паспорта и сертификаты ГПМ", "partner"),
                   ("Чертежи и планы объектов", "partner"), ("Фото с объектов", "internal"),
                   ("Акты и счета", "internal"), ("Входящие", "internal")]


def ensure_folders(tenant: Tenant) -> list[DocFolder]:
    """Базовый набор рабочих пространств — чтобы документы не сваливались в одну кучу."""
    existing = db.query(DocFolder).filter_by(tenant_id=tenant.id).count()
    if existing:
        return db.query(DocFolder).filter_by(tenant_id=tenant.id).order_by(DocFolder.sequence).all()
    out = []
    for i, (name, access) in enumerate(DEFAULT_FOLDERS):
        f = DocFolder(tenant_id=tenant.id, name=name, access=access, sequence=(i + 1) * 10)
        db.add(f)
        out.append(f)
    db.commit()
    return out


def tree(tenant: Tenant) -> list[dict]:
    folders = db.query(DocFolder).filter_by(tenant_id=tenant.id).order_by(DocFolder.sequence, DocFolder.id).all()
    counts = dict(db.query(Media.folder_id, func.count(Media.id))
                  .filter(Media.tenant_id == tenant.id).group_by(Media.folder_id).all())
    by_parent: dict[int | None, list[DocFolder]] = {}
    for f in folders:
        by_parent.setdefault(f.parent_id, []).append(f)

    def pack(folder: DocFolder, level: int) -> list[dict]:
        rows = [{"folder": folder, "level": level, "count": counts.get(folder.id, 0)}]
        for kid in by_parent.get(folder.id, []):
            rows += pack(kid, level + 1)
        return rows

    out: list[dict] = []
    for root in by_parent.get(None, []):
        out += pack(root, 0)
    return out


def files(tenant: Tenant, *, folder_id=None, tag: str = "", query: str = "", entity: str = "",
          entity_id=None, only_current: bool = True) -> list[Media]:
    q = db.query(Media).filter(Media.tenant_id == tenant.id)
    if folder_id:
        q = q.filter(Media.folder_id == folder_id)
    if tag:
        q = q.filter(Media.tags.like(f"%{tag}%"))
    if entity:
        q = q.filter(Media.entity == entity)
        if entity_id:
            q = q.filter(Media.entity_id == entity_id)
    if query:
        like = f"%{query}%"
        q = q.filter(or_(Media.filename.like(like), Media.tags.like(like), Media.note.like(like)))
    if only_current:
        q = q.filter(Media.version_of_id.is_(None))     # версии показываем внутри карточки файла
    return q.order_by(Media.created_at.desc()).all()


def versions(media: Media) -> list[Media]:
    return (db.query(Media).filter_by(version_of_id=media.id)
            .order_by(Media.version.desc()).all())


def add_version(tenant: Tenant, current: Media, new_media: Media, note: str = "") -> Media:
    """Новая версия: прежний файл уходит в историю, актуальным остаётся один."""
    history = versions(current)
    new_media.version = (current.version or 1) + 1
    new_media.folder_id = current.folder_id
    new_media.entity, new_media.entity_id = current.entity, current.entity_id
    new_media.tags = current.tags
    new_media.note = note or current.note
    db.flush()
    # прежняя актуальная запись и вся её история привязываются к новой
    current.version_of_id = new_media.id
    for old in history:
        old.version_of_id = new_media.id
    db.commit()
    return new_media


def link_to(media: Media, entity: str, entity_id: int) -> Media:
    media.entity, media.entity_id = entity, entity_id
    db.commit()
    return media


def set_tags(media: Media, tags: str) -> Media:
    media.tags = ", ".join(sorted({t.strip() for t in tags.split(",") if t.strip()}))[:200]
    db.commit()
    return media


def all_tags(tenant: Tenant) -> list[tuple[str, int]]:
    counter: dict[str, int] = {}
    for (tags,) in db.query(Media.tags).filter(Media.tenant_id == tenant.id, Media.tags != "").all():
        for t in (tags or "").split(","):
            t = t.strip()
            if t:
                counter[t] = counter.get(t, 0) + 1
    return sorted(counter.items(), key=lambda kv: -kv[1])


# ------------------------------------------------------------------ запросы документов

def request_document(tenant: Tenant, *, name: str, to_email: str = "", to_name: str = "",
                     folder_id=None, due_on: date | None = None, entity: str = "",
                     entity_id=None, send: bool = True) -> DocRequest:
    req = DocRequest(tenant_id=tenant.id, name=name[:200], to_email=to_email.strip().lower(),
                     to_name=to_name[:160], folder_id=folder_id, due_on=due_on,
                     entity=entity, entity_id=entity_id)
    db.add(req)
    db.commit()
    if send and req.to_email:
        notify_request(tenant, req)
    return req


def notify_request(tenant: Tenant, req: DocRequest, base_url: str = "") -> None:
    from ..mailer import send_mail
    link = f"{base_url}/upload/{req.request_token}" if base_url else f"по ссылке с кодом {req.request_token}"
    due = f" до {req.due_on:%d.%m.%Y}" if req.due_on else ""
    send_mail(tenant, req.to_email, f"Нужен документ: {req.name}",
              f"Здравствуйте{', ' + req.to_name if req.to_name else ''}!\n\n"
              f"Для продолжения работ нужен документ «{req.name}»{due}.\n"
              f"Загрузите его {link}.\n\nС уважением, {tenant.name}")


def fulfil_request(req: DocRequest, media: Media) -> DocRequest:
    req.media_id = media.id
    req.status = "received"
    req.received_at = datetime.utcnow()
    if req.folder_id:
        media.folder_id = req.folder_id
    if req.entity:
        media.entity, media.entity_id = req.entity, req.entity_id
    db.commit()
    return req


def pending_requests(tenant: Tenant) -> list[DocRequest]:
    return (db.query(DocRequest).filter_by(tenant_id=tenant.id, status="pending")
            .order_by(DocRequest.due_on.is_(None), DocRequest.due_on).all())


# ------------------------------------------------------------------ правила обработки

def apply_rules(tenant: Tenant, media: Media) -> list[str]:
    """Автообработка входящего файла: разложить по папкам, пометить, поставить задачу."""
    applied = []
    rules = db.query(DocRule).filter_by(tenant_id=tenant.id, is_active=True).order_by(DocRule.id).all()
    for rule in rules:
        if rule.match_tag and rule.match_tag.lower() not in (media.tags or "").lower() \
                and rule.match_tag.lower() not in (media.filename or "").lower():
            continue
        if rule.match_mime and rule.match_mime.lower() not in (media.mime or "").lower():
            continue
        params = rule.params or {}
        if rule.action == "move" and params.get("folder_id"):
            media.folder_id = int(params["folder_id"])
        elif rule.action == "tag" and params.get("tags"):
            merged = ", ".join(filter(None, [media.tags, params["tags"]]))
            set_tags(media, merged)
        elif rule.action == "task":
            db.add(Task(tenant_id=tenant.id, title=params.get("title") or f"Обработать файл: {media.filename}",
                        description=f"Файл {media.filename} загружен {media.created_at:%d.%m.%Y}",
                        stage="todo", priority=int(params.get("priority", 0)),
                        assignee_id=params.get("assignee_id")))
        elif rule.action == "notify" and params.get("email"):
            from ..mailer import send_mail
            send_mail(tenant, params["email"], f"Новый документ: {media.filename}",
                      f"В рабочее пространство загружен файл {media.filename}.")
        rule.runs = (rule.runs or 0) + 1
        applied.append(rule.name)
    db.commit()
    return applied


def expiring(tenant: Tenant, days: int = 30) -> list[Media]:
    """Документы с истекающим сроком: страховки, сертификаты, паспорта ГПМ."""
    from datetime import timedelta
    limit = date.today() + timedelta(days=days)
    return (db.query(Media).filter(Media.tenant_id == tenant.id, Media.expires_on.isnot(None),
                                   Media.expires_on <= limit)
            .order_by(Media.expires_on).all())


def summary(tenant: Tenant) -> dict:
    total = db.query(func.count(Media.id)).filter_by(tenant_id=tenant.id).scalar() or 0
    size = db.query(func.coalesce(func.sum(Media.size), 0)).filter_by(tenant_id=tenant.id).scalar() or 0
    return {"files": total, "size_mb": round(float(size) / 1024 / 1024, 1),
            "folders": db.query(func.count(DocFolder.id)).filter_by(tenant_id=tenant.id).scalar() or 0,
            "pending": len(pending_requests(tenant)), "expiring": len(expiring(tenant)),
            "tags": len(all_tags(tenant))}
