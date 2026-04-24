"""Magic link 公开填报 API — 供应商拿链接直接填,不用注册登录

方式4混合模型:
- 供应商可以手填报价清单(rows)
- 也可以上传 PDF/Excel/图片 → (未来)AI 自动解析成 rows
- 支持同时存在,供应商校对

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
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from app.db import get_session
from app.models.inquiry import Inquiry, InquiryInvite, InquiryItem, InquiryStatus, QuoteLine
from app.models.quote import QuoteAttachment, QuoteRow, QuoteRowSource
from app.models.supplier import Supplier
from app.schemas.inquiry import (
    PublicAttachmentRead,
    PublicInquiryItem,
    PublicQuoteRow,
    PublicQuoteSubmit,
    PublicQuoteView,
)

router = APIRouter(prefix="/public/quote", tags=["public-quote"])

# 文件存储根目录 (docker volume mount 到 /app/uploads)
UPLOAD_ROOT = Path(os.environ.get("SRM_UPLOAD_ROOT", "/app/uploads"))
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_MIMES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # xlsx
    "application/vnd.ms-excel",  # xls
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # docx
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

    # 方式4:供应商自己列的行
    rows = session.exec(
        select(QuoteRow)
        .where(
            QuoteRow.inquiry_id == inquiry.id,
            QuoteRow.supplier_id == supplier.id,
        )
        .order_by(QuoteRow.sort_order, QuoteRow.id)
    ).all()
    row_views = [PublicQuoteRow.model_validate(r) for r in rows]

    # 附件
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
    """提交报价 — 方式4: rows 覆盖式;方式1兼容: preset_quotes 对应 InquiryItem"""
    invite = _load_invite_by_token(session, token)
    inquiry = session.get(Inquiry, invite.inquiry_id)
    if not inquiry:
        raise HTTPException(404, "询价单不存在")
    if inquiry.status == InquiryStatus.CLOSED:
        raise HTTPException(400, "此询价单已关闭,无法再修改报价")

    now = datetime.now(UTC)
    submitted_any = False

    # 方式4:覆盖式更新 rows
    if payload.rows:
        # 先清旧
        old_rows = session.exec(
            select(QuoteRow).where(
                QuoteRow.inquiry_id == inquiry.id,
                QuoteRow.supplier_id == invite.supplier_id,
            )
        ).all()
        for r in old_rows:
            session.delete(r)
        # 再插新
        for idx, row in enumerate(payload.rows):
            if not row.name or not row.name.strip():
                continue
            try:
                src = QuoteRowSource(row.source) if row.source else QuoteRowSource.MANUAL
            except ValueError:
                src = QuoteRowSource.MANUAL
            session.add(QuoteRow(
                inquiry_id=inquiry.id,
                supplier_id=invite.supplier_id,
                name=row.name.strip(),
                spec=row.spec,
                unit=row.unit or "个",
                qty=row.qty,
                unit_price=row.unit_price,
                note=row.note,
                source=src,
                sort_order=idx,
            ))
        submitted_any = True

    # 方式1:填预设 InquiryItem 的单价
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
        submitted_any = True

    if not submitted_any:
        # 允许"只上传附件不填 rows"吗?是的 — 仅当已有附件时
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

    session.commit()

    ip = request.client.host if request.client else "?"
    print(f"[public-quote] submit token={token[:8]}... inquiry={inquiry.code} "
          f"supplier_id={invite.supplier_id} rows={len(payload.rows)} preset={len(payload.preset_quotes)} ip={ip}",
          flush=True)

    session.refresh(invite)
    return _build_view(session, invite)


# ============== 附件上传 ==============

def _safe_filename(name: str) -> str:
    """去掉路径分隔符等危险字符"""
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
    if inquiry.status == InquiryStatus.CLOSED:
        raise HTTPException(400, "此询价单已关闭,无法再上传附件")

    # MIME 检查
    mime = file.content_type or mimetypes.guess_type(file.filename or "")[0] or "application/octet-stream"
    if mime not in ALLOWED_MIMES:
        raise HTTPException(400, f"不支持的文件类型: {mime}。允许 PDF/Excel/Word/图片/CSV")

    # 读文件 + 大小检查
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(400, f"文件过大,最大 {MAX_FILE_SIZE // 1024 // 1024} MB")
    if len(content) == 0:
        raise HTTPException(400, "空文件")

    # 写盘
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
    if inquiry and inquiry.status == InquiryStatus.CLOSED:
        raise HTTPException(400, "此询价单已关闭,无法删除附件")
    # 删文件(忽略文件系统错误,数据库记录是主源)
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
    """供应商/采购员都能下载自己(或自家)的附件
    — 为了简化,public 入口只要 token 对就能下;采购员有另一条带 auth 的路径
    """
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


@router.post("/{token}/attachment/{attachment_id}/parse", response_model=PublicQuoteView)
def parse_attachment(
    token: str,
    attachment_id: int,
    session: Session = Depends(get_session),
) -> PublicQuoteView:
    """触发 AI 解析附件 — 目前是占位,标记 parse_status=skipped
    等丽丽把 MiniMax/Claude API key 给后端配上,换成真调用
    """
    invite = _load_invite_by_token(session, token)
    att = session.get(QuoteAttachment, attachment_id)
    if not att or att.inquiry_id != invite.inquiry_id or att.supplier_id != invite.supplier_id:
        raise HTTPException(404, "附件不存在")
    # TODO: 调 MiniMax/Claude Vision → 解出 rows → 批量插入 QuoteRow(source=ai_parsed)
    att.parse_status = "skipped"
    att.parse_note = "AI 解析功能开发中,暂时请在下方表格手动填写。"
    att.parsed_at = datetime.now(UTC)
    session.add(att)
    session.commit()
    return _build_view(session, invite)
