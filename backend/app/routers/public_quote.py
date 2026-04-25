"""Magic link 公开填报 API — 供应商拿链接直接填,不用注册登录

版本化模型(v3):
- 每次 PUT /quote 创建一个 QuoteRevision,rows 挂其下
- 视图默认返回最新 revision 的 rows(作为编辑起点)
- 历史版本保留,采购员可查调价轨迹
- /parse 不再入库,只返回 rows 数据让前端填表,供应商校对后提交才入库

安全:
- token 32字节 URL-safe 随机,每家独立
- 视图完全隔离,不含其他供应商信息
- 询价单关闭后 PUT/上传 拒绝
- 提交记 IP 审计
"""

import mimetypes
import os
import secrets
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from app import llm
from app.db import get_session
from app.models.inquiry import Inquiry, InquiryInvite, InquiryItem, InquiryStatus, QuoteLine
from app.models.quote import QuoteAttachment, QuoteRevision, QuoteRow, QuoteRowSource
from app.models.supplier import Supplier
from app.schemas.inquiry import (
    ParseAttachmentResult,
    ParsedRow,
    PublicAttachmentRead,
    PublicInquiryItem,
    PublicQuoteRow,
    PublicQuoteSubmit,
    PublicQuoteView,
)

router = APIRouter(prefix="/public/quote", tags=["public-quote"])

UPLOAD_ROOT = Path(os.environ.get("SRM_UPLOAD_ROOT", "/app/uploads"))
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_MIMES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "image/jpeg", "image/png", "image/webp", "image/gif",
    "text/csv", "text/plain",
}


def _load_invite_by_token(session: Session, token: str) -> InquiryInvite:
    if not token or len(token) < 16:
        raise HTTPException(404, "链接无效或已过期")
    invite = session.exec(select(InquiryInvite).where(InquiryInvite.token == token)).first()
    if not invite:
        raise HTTPException(404, "链接无效或已过期")
    return invite


def _is_expired(inquiry: Inquiry) -> bool:
    """是否已过报价截止时间。无截止时间则永不过期。"""
    if not inquiry.quote_deadline:
        return False
    deadline = inquiry.quote_deadline
    # 兼容数据库里存的是 naive datetime 的情况
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=UTC)
    return datetime.now(UTC) > deadline


def _ensure_writable(inquiry: Inquiry) -> None:
    """统一的写操作前置:已关闭/已截止则拒绝。"""
    if inquiry.status == InquiryStatus.CLOSED:
        raise HTTPException(400, "此询价单已关闭,无法再修改报价")
    if _is_expired(inquiry):
        raise HTTPException(400, "此询价单已过报价截止时间,无法再修改报价")


def _latest_revision(session: Session, inquiry_id: int, supplier_id: int) -> QuoteRevision | None:
    return session.exec(
        select(QuoteRevision)
        .where(
            QuoteRevision.inquiry_id == inquiry_id,
            QuoteRevision.supplier_id == supplier_id,
        )
        .order_by(QuoteRevision.version.desc())
        .limit(1)
    ).first()


def _latest_rows(session: Session, inquiry_id: int, supplier_id: int) -> list[QuoteRow]:
    rev = _latest_revision(session, inquiry_id, supplier_id)
    if not rev:
        return []
    return session.exec(
        select(QuoteRow)
        .where(QuoteRow.revision_id == rev.id)
        .order_by(QuoteRow.sort_order, QuoteRow.id)
    ).all()


def _build_view(session: Session, invite: InquiryInvite) -> PublicQuoteView:
    inquiry = session.get(Inquiry, invite.inquiry_id)
    if not inquiry:
        raise HTTPException(404, "询价单不存在")
    supplier = session.get(Supplier, invite.supplier_id)
    if not supplier:
        raise HTTPException(404, "供应商不存在")

    # 方式1兼容:采购员预设的骨架物料(如有)
    preset_items = session.exec(
        select(InquiryItem)
        .where(InquiryItem.inquiry_id == inquiry.id)
        .order_by(InquiryItem.sort_order, InquiryItem.id)
    ).all()
    preset_quotes = session.exec(
        select(QuoteLine).where(
            QuoteLine.inquiry_id == inquiry.id,
            QuoteLine.supplier_id == supplier.id,
        )
    ).all()
    qb_item = {q.inquiry_item_id: q for q in preset_quotes}
    preset_views = []
    for it in preset_items:
        line = qb_item.get(it.id)
        preset_views.append(PublicInquiryItem(
            id=it.id, name=it.name, spec=it.spec, unit=it.unit, qty=it.qty,
            remark=it.remark, sort_order=it.sort_order,
            my_unit_price=line.unit_price if line else None,
            my_note=line.note if line else None,
        ))

    # 方式4:最新 revision 的 rows 作为编辑起点
    rows = _latest_rows(session, inquiry.id, supplier.id)
    row_views = [PublicQuoteRow.model_validate(r) for r in rows]

    atts = session.exec(
        select(QuoteAttachment)
        .where(
            QuoteAttachment.inquiry_id == inquiry.id,
            QuoteAttachment.supplier_id == supplier.id,
        )
        .order_by(QuoteAttachment.uploaded_at)
    ).all()
    att_views = [PublicAttachmentRead.model_validate(a) for a in atts]

    return PublicQuoteView(
        code=inquiry.code,
        title=inquiry.title,
        remark=inquiry.remark,
        delivery_date=inquiry.delivery_date,
        quote_deadline=inquiry.quote_deadline,
        is_expired=_is_expired(inquiry),
        supplier_company_name=supplier.company_name,
        status=inquiry.status,
        created_at=inquiry.created_at,
        quoted_at=invite.quoted_at,
        preset_items=preset_views,
        rows=row_views,
        attachments=att_views,
    )


@router.get("/{token}", response_model=PublicQuoteView)
def view_quote(token: str, session: Session = Depends(get_session)) -> PublicQuoteView:
    invite = _load_invite_by_token(session, token)
    return _build_view(session, invite)


@router.put("/{token}", response_model=PublicQuoteView)
def submit_quote(
    token: str,
    payload: PublicQuoteSubmit,
    request: Request,
    session: Session = Depends(get_session),
) -> PublicQuoteView:
    """提交报价 — 每次创建新 QuoteRevision 快照。
    方式1兼容:preset_quotes 对应 InquiryItem 单独走 QuoteLine 表。
    """
    invite = _load_invite_by_token(session, token)
    inquiry = session.get(Inquiry, invite.inquiry_id)
    if not inquiry:
        raise HTTPException(404, "询价单不存在")
    _ensure_writable(inquiry)

    now = datetime.now(UTC)
    ip = request.client.host if request.client else None
    submitted_rows = False
    submitted_preset = False

    # ========== 方式4:创建新 revision + 插入 rows ==========
    if payload.rows:
        # 规整化 + 计算合计
        valid_rows = []
        total = Decimal("0")
        sources = set()
        for idx, row in enumerate(payload.rows):
            if not row.name or not row.name.strip():
                continue
            try:
                src = QuoteRowSource(row.source) if row.source else QuoteRowSource.MANUAL
            except ValueError:
                src = QuoteRowSource.MANUAL
            sources.add(src.value)
            qty = row.qty
            price = row.unit_price
            if qty is not None and qty > 0:
                total += qty * price
            else:
                total += price
            valid_rows.append((idx, row, src))

        if not valid_rows:
            raise HTTPException(400, "报价行全部为空,请至少填写一行")

        # 版本号:现有最大 +1
        latest = _latest_revision(session, inquiry.id, invite.supplier_id)
        new_version = (latest.version + 1) if latest else 1

        source_summary = (
            list(sources)[0] if len(sources) == 1 else "mixed"
        )

        has_att = session.exec(
            select(QuoteAttachment).where(
                QuoteAttachment.inquiry_id == inquiry.id,
                QuoteAttachment.supplier_id == invite.supplier_id,
            )
        ).first() is not None

        rev = QuoteRevision(
            inquiry_id=inquiry.id,
            supplier_id=invite.supplier_id,
            version=new_version,
            committed_at=now,
            total_amount=total,
            row_count=len(valid_rows),
            source_summary=source_summary,
            has_attachment=has_att,
            client_ip=ip,
        )
        session.add(rev)
        session.flush()  # 拿到 rev.id

        for idx, row, src in valid_rows:
            session.add(QuoteRow(
                inquiry_id=inquiry.id,
                supplier_id=invite.supplier_id,
                revision_id=rev.id,
                name=row.name.strip()[:128],
                spec=(row.spec or "").strip()[:256] or None,
                unit=(row.unit or "个").strip()[:16] or "个",
                qty=row.qty,
                unit_price=row.unit_price,
                note=(row.note or "").strip()[:256] or None,
                source=src,
                sort_order=idx,
            ))
        submitted_rows = True

    # ========== 方式1兼容:preset_quotes(采购员预设物料) ==========
    if payload.preset_quotes:
        items = session.exec(
            select(InquiryItem).where(InquiryItem.inquiry_id == inquiry.id)
        ).all()
        valid_item_ids = {i.id for i in items}
        for pq in payload.preset_quotes:
            if pq.item_id not in valid_item_ids:
                raise HTTPException(400, f"物料行 {pq.item_id} 不属于此询价单")

        existing = session.exec(
            select(QuoteLine).where(
                QuoteLine.inquiry_id == inquiry.id,
                QuoteLine.supplier_id == invite.supplier_id,
            )
        ).all()
        existing_by_item = {q.inquiry_item_id: q for q in existing}
        for pq in payload.preset_quotes:
            cur = existing_by_item.get(pq.item_id)
            if cur:
                cur.unit_price = pq.unit_price
                cur.note = pq.note
                cur.updated_at = now
                session.add(cur)
            else:
                session.add(QuoteLine(
                    inquiry_id=inquiry.id,
                    inquiry_item_id=pq.item_id,
                    supplier_id=invite.supplier_id,
                    unit_price=pq.unit_price,
                    note=pq.note,
                ))
        submitted_preset = True

    if not submitted_rows and not submitted_preset:
        # 允许"只上传附件不填 rows"仅当已有附件时 — 此分支不新建 revision
        have_att = session.exec(
            select(QuoteAttachment).where(
                QuoteAttachment.inquiry_id == inquiry.id,
                QuoteAttachment.supplier_id == invite.supplier_id,
            )
        ).first()
        if not have_att:
            raise HTTPException(400, "请至少填写一行报价或上传一份报价附件")

    if not invite.quoted_at:
        invite.quoted_at = now
        session.add(invite)
    else:
        # 二次及以上提交也更新时间(便于列表看"最新提交时间")
        invite.quoted_at = now
        session.add(invite)

    session.commit()

    print(f"[public-quote] submit token={token[:8]}... inquiry={inquiry.code} "
          f"supplier_id={invite.supplier_id} rows_submitted={submitted_rows} "
          f"preset_submitted={submitted_preset} ip={ip}", flush=True)

    session.refresh(invite)
    return _build_view(session, invite)


# ============== 附件上传/下载/删除 ==============

def _safe_filename(name: str) -> str:
    bad = "/\\:*?\"<>|\0"
    cleaned = "".join(c for c in name if c not in bad).strip()
    return cleaned[:200] or "upload"


@router.post("/{token}/attachment", response_model=PublicAttachmentRead, status_code=201)
async def upload_attachment(
    token: str,
    request: Request,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> PublicAttachmentRead:
    invite = _load_invite_by_token(session, token)
    inquiry = session.get(Inquiry, invite.inquiry_id)
    if not inquiry:
        raise HTTPException(404, "询价单不存在")
    _ensure_writable(inquiry)

    mime = file.content_type or mimetypes.guess_type(file.filename or "")[0] or "application/octet-stream"
    if mime not in ALLOWED_MIMES:
        raise HTTPException(400, f"不支持的文件类型: {mime}。允许 PDF/Excel/Word/图片/CSV")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(400, f"文件过大,最大 {MAX_FILE_SIZE // 1024 // 1024} MB")
    if len(content) == 0:
        raise HTTPException(400, "空文件")

    rel_dir = f"quote/{inquiry.id}/{invite.supplier_id}"
    disk_dir = UPLOAD_ROOT / rel_dir
    disk_dir.mkdir(parents=True, exist_ok=True)

    safe_name = _safe_filename(file.filename or "upload")
    stamp = secrets.token_urlsafe(6)
    disk_name = f"{stamp}_{safe_name}"
    disk_path = disk_dir / disk_name
    with open(disk_path, "wb") as f:
        f.write(content)

    rec = QuoteAttachment(
        inquiry_id=inquiry.id,
        supplier_id=invite.supplier_id,
        filename=safe_name,
        storage_path=f"{rel_dir}/{disk_name}",
        file_size=len(content),
        mime_type=mime,
        parse_status="pending",
    )
    session.add(rec)
    session.commit()
    session.refresh(rec)

    ip = request.client.host if request.client else "?"
    print(f"[public-quote] upload token={token[:8]}... inquiry={inquiry.code} "
          f"supplier_id={invite.supplier_id} file={safe_name} size={len(content)} ip={ip}",
          flush=True)

    return PublicAttachmentRead.model_validate(rec)


@router.delete("/{token}/attachment/{attachment_id}", status_code=204)
def delete_attachment(
    token: str,
    attachment_id: int,
    session: Session = Depends(get_session),
) -> None:
    invite = _load_invite_by_token(session, token)
    att = session.get(QuoteAttachment, attachment_id)
    if not att or att.inquiry_id != invite.inquiry_id or att.supplier_id != invite.supplier_id:
        raise HTTPException(404, "附件不存在")
    inquiry = session.get(Inquiry, invite.inquiry_id)
    if inquiry:
        _ensure_writable(inquiry)
    try:
        disk_path = UPLOAD_ROOT / att.storage_path
        if disk_path.exists():
            disk_path.unlink()
    except Exception:
        pass
    session.delete(att)
    session.commit()


@router.get("/{token}/attachment/{attachment_id}/download")
def download_attachment(
    token: str,
    attachment_id: int,
    session: Session = Depends(get_session),
):
    invite = _load_invite_by_token(session, token)
    att = session.get(QuoteAttachment, attachment_id)
    if not att or att.inquiry_id != invite.inquiry_id or att.supplier_id != invite.supplier_id:
        raise HTTPException(404, "附件不存在")
    disk_path = UPLOAD_ROOT / att.storage_path
    if not disk_path.exists():
        raise HTTPException(404, "文件已丢失")
    return FileResponse(
        path=str(disk_path),
        filename=att.filename,
        media_type=att.mime_type,
    )


# ============== AI 解析 — 不再入库,返回数据给前端渲染 ==============

@router.post("/{token}/attachment/{attachment_id}/parse", response_model=ParseAttachmentResult)
def parse_attachment_endpoint(
    token: str,
    attachment_id: int,
    session: Session = Depends(get_session),
) -> ParseAttachmentResult:
    """调 MiniMax 解析附件 → 返回 rows 数据给前端渲染。
    不入库 — 供应商校对后点"提交报价"才会落版本。
    """
    invite = _load_invite_by_token(session, token)
    att = session.get(QuoteAttachment, attachment_id)
    if not att or att.inquiry_id != invite.inquiry_id or att.supplier_id != invite.supplier_id:
        raise HTTPException(404, "附件不存在")

    if not llm.is_configured():
        att.parse_status = "skipped"
        att.parse_note = "AI 解析暂未配置,请手动填写明细。"
        att.parsed_at = datetime.now(UTC)
        session.add(att)
        session.commit()
        return ParseAttachmentResult(
            ok=False, attachment_id=att.id,
            parse_status=att.parse_status, parse_note=att.parse_note,
        )

    att.parse_status = "parsing"
    session.add(att)
    session.commit()

    disk_path = UPLOAD_ROOT / att.storage_path
    result = llm.parse_attachment(disk_path, att.mime_type)

    if not result.get("ok"):
        att.parse_status = "failed"
        att.parse_note = (result.get("error") or "解析失败")[:500]
        att.parsed_at = datetime.now(UTC)
        session.add(att)
        session.commit()
        return ParseAttachmentResult(
            ok=False, attachment_id=att.id,
            parse_status="failed", parse_note=att.parse_note,
        )

    raw_rows = result.get("rows") or []
    parsed: list[ParsedRow] = []
    for r in raw_rows:
        name = (r.get("name") or "").strip()
        if not name:
            continue
        try:
            price = Decimal(str(r.get("unit_price")))
            if price <= 0:
                continue
        except (InvalidOperation, TypeError):
            continue
        qty = None
        if r.get("qty") is not None:
            try:
                qty = Decimal(str(r["qty"]))
                if qty <= 0:
                    qty = None
            except (InvalidOperation, TypeError):
                qty = None
        parsed.append(ParsedRow(
            name=name[:128],
            spec=(r.get("spec") or "").strip()[:256] or None,
            unit=(r.get("unit") or "个").strip()[:16] or "个",
            qty=qty,
            unit_price=price,
            note=(r.get("note") or "").strip()[:256] or None,
        ))

    ok = len(parsed) > 0
    att.parse_status = "done" if ok else "failed"
    att.parse_note = f"识别出 {len(parsed)} 行,请核对后提交" if ok else "未能识别出任何有效报价行,请手动填写"
    att.parsed_at = datetime.now(UTC)
    session.add(att)
    session.commit()

    print(f"[llm-parse] attachment={attachment_id} mime={att.mime_type} "
          f"rows={len(raw_rows)} valid={len(parsed)}", flush=True)

    return ParseAttachmentResult(
        ok=ok,
        attachment_id=att.id,
        parse_status=att.parse_status,
        parse_note=att.parse_note,
        rows=parsed,
    )
