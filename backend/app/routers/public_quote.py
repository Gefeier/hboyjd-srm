"""Magic link 公开填报 API — 供应商拿链接直接填,不用注册登录

安全模型:
- token 32字节 URL-safe 随机,每家独立,泄露只影响这一张单的这一家
- 询价单关闭后 PUT 被拒,GET 还能看(只读历史报价)
- 视图里不含其他供应商/其他家报价/采购员任何信息
- 提交时记录 IP 用于事后审计
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlmodel import Session, select

from app.db import get_session
from app.models.inquiry import Inquiry, InquiryInvite, InquiryItem, InquiryStatus, QuoteLine
from app.models.supplier import Supplier
from app.schemas.inquiry import PublicInquiryItem, PublicQuoteSubmit, PublicQuoteView

router = APIRouter(prefix="/public/quote", tags=["public-quote"])


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

    items = session.exec(
        select(InquiryItem)
        .where(InquiryItem.inquiry_id == inquiry.id)
        .order_by(InquiryItem.sort_order, InquiryItem.id)
    ).all()
    my_lines = session.exec(
        select(QuoteLine).where(
            QuoteLine.inquiry_id == inquiry.id,
            QuoteLine.supplier_id == supplier.id,
        )
    ).all()
    my_lines_by_item = {line.inquiry_item_id: line for line in my_lines}

    item_views = []
    for it in items:
        line = my_lines_by_item.get(it.id)
        item_views.append(PublicInquiryItem(
            id=it.id,
            name=it.name,
            spec=it.spec,
            unit=it.unit,
            qty=it.qty,
            remark=it.remark,
            sort_order=it.sort_order,
            my_unit_price=line.unit_price if line else None,
            my_note=line.note if line else None,
        ))

    return PublicQuoteView(
        code=inquiry.code,
        title=inquiry.title,
        remark=inquiry.remark,
        delivery_date=inquiry.delivery_date,
        delivery_address=inquiry.delivery_address,
        supplier_company_name=supplier.company_name,
        status=inquiry.status,
        created_at=inquiry.created_at,
        quoted_at=invite.quoted_at,
        items=item_views,
    )


@router.get("/{token}", response_model=PublicQuoteView)
def view_quote(
    token: str,
    session: Session = Depends(get_session),
) -> PublicQuoteView:
    invite = _load_invite_by_token(session, token)
    return _build_view(session, invite)


@router.put("/{token}", response_model=PublicQuoteView)
def submit_quote(
    token: str,
    payload: PublicQuoteSubmit,
    request: Request,
    session: Session = Depends(get_session),
) -> PublicQuoteView:
    invite = _load_invite_by_token(session, token)
    inquiry = session.get(Inquiry, invite.inquiry_id)
    if not inquiry:
        raise HTTPException(404, "询价单不存在")
    if inquiry.status == InquiryStatus.CLOSED:
        raise HTTPException(400, "此询价单已关闭,无法再修改报价")

    # 校验所有 item_id 都属于这张单
    items = session.exec(
        select(InquiryItem).where(InquiryItem.inquiry_id == inquiry.id)
    ).all()
    valid_item_ids = {i.id for i in items}
    for line in payload.lines:
        if line.item_id not in valid_item_ids:
            raise HTTPException(400, f"物料行 {line.item_id} 不属于此询价单")

    # Upsert
    existing = session.exec(
        select(QuoteLine).where(
            QuoteLine.inquiry_id == inquiry.id,
            QuoteLine.supplier_id == invite.supplier_id,
        )
    ).all()
    existing_by_item = {q.inquiry_item_id: q for q in existing}
    now = datetime.now(UTC)

    for line in payload.lines:
        existing_line = existing_by_item.get(line.item_id)
        if existing_line:
            existing_line.unit_price = line.unit_price
            existing_line.note = line.note
            existing_line.updated_at = now
            session.add(existing_line)
        else:
            session.add(QuoteLine(
                inquiry_id=inquiry.id,
                inquiry_item_id=line.item_id,
                supplier_id=invite.supplier_id,
                unit_price=line.unit_price,
                note=line.note,
            ))

    if not invite.quoted_at:
        invite.quoted_at = now
        session.add(invite)

    session.commit()

    # 轻量审计:写一行日志(stdout→docker logs 留痕)
    ip = request.client.host if request.client else "?"
    print(f"[public-quote] submit token={token[:8]}... inquiry={inquiry.code} supplier_id={invite.supplier_id} lines={len(payload.lines)} ip={ip}", flush=True)

    session.refresh(invite)
    return _build_view(session, invite)
