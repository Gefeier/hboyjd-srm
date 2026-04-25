"""比价单(询价单) — 采购员建单,供应商填价,采购部内部比价"""

import os
import secrets
from datetime import UTC, datetime, time
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from sqlalchemy import func
from sqlmodel import Session, select

from app.db import get_session
from app.deps import get_current_supplier, get_current_user, require_buyer_or_admin
from app.models.inquiry import Inquiry, InquiryInvite, InquiryItem, InquiryStatus, QuoteLine
from app.models.quote import QuoteAttachment, QuoteRevision, QuoteRow
from app.models.supplier import Supplier, SupplierStatus
from app.models.user import User
from app.schemas.inquiry import (
    AdminAttachment,
    AdminQuoteRow,
    InquiryAwardRequest,
    InquiryCreate,
    InquiryDetail,
    InquiryUpdate,
    InquiryItemRead,
    InquiryListResponse,
    InquiryRead,
    InquirySupplierQuotesResponse,
    InviteRead,
    MyInquiryDetail,
    MyInquiryItem,
    MyQuoteSubmit,
    QuoteLineRead,
    RevisionRow,
    RevisionSnapshot,
    SupplierHistoryResponse,
    SupplierMini,
    SupplierQuoteDetail,
)

UPLOAD_ROOT = Path(os.environ.get("SRM_UPLOAD_ROOT", "/app/uploads"))

router = APIRouter(prefix="/inquiries", tags=["inquiries"])


def generate_inquiry_code(session: Session) -> str:
    now = datetime.now(UTC)
    day_start = datetime.combine(now.date(), time.min, tzinfo=UTC)
    day_end = datetime.combine(now.date(), time.max, tzinfo=UTC)
    stmt = select(func.count()).select_from(Inquiry).where(
        Inquiry.created_at >= day_start, Inquiry.created_at <= day_end
    )
    count = session.exec(stmt).one()
    return f"RFQ{now:%Y%m%d}{count + 1:03d}"


def _build_inquiry_read(inquiry: Inquiry, session: Session) -> InquiryRead:
    """带汇总的列表视图"""
    buyer = session.get(User, inquiry.buyer_id)
    awarded = session.get(Supplier, inquiry.awarded_supplier_id) if inquiry.awarded_supplier_id else None
    item_count = session.exec(
        select(func.count()).select_from(InquiryItem).where(InquiryItem.inquiry_id == inquiry.id)
    ).one()
    invited_count = session.exec(
        select(func.count()).select_from(InquiryInvite).where(InquiryInvite.inquiry_id == inquiry.id)
    ).one()
    quoted_count = session.exec(
        select(func.count()).select_from(InquiryInvite).where(
            InquiryInvite.inquiry_id == inquiry.id,
            InquiryInvite.quoted_at.isnot(None),
        )
    ).one()
    return InquiryRead(
        id=inquiry.id,
        code=inquiry.code,
        title=inquiry.title,
        remark=inquiry.remark,
        buyer_id=inquiry.buyer_id,
        buyer_name=buyer.name if buyer else None,
        status=inquiry.status,
        delivery_date=inquiry.delivery_date,
        delivery_address=inquiry.delivery_address,
        awarded_supplier_id=inquiry.awarded_supplier_id,
        awarded_supplier_name=awarded.company_name if awarded else None,
        closed_at=inquiry.closed_at,
        created_at=inquiry.created_at,
        updated_at=inquiry.updated_at,
        item_count=item_count,
        invited_count=invited_count,
        quoted_count=quoted_count,
    )


# ============== 采购员端 ==============

@router.post("", response_model=InquiryDetail, status_code=status.HTTP_201_CREATED)
def create_inquiry(
    payload: InquiryCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_buyer_or_admin),
) -> InquiryDetail:
    # 验:供应商必须存在且非冻结
    suppliers = session.exec(select(Supplier).where(Supplier.id.in_(payload.supplier_ids))).all()
    valid_ids = {s.id for s in suppliers if s.status != SupplierStatus.FROZEN}
    missing = set(payload.supplier_ids) - {s.id for s in suppliers}
    if missing:
        raise HTTPException(400, f"供应商不存在: {sorted(missing)}")
    frozen = set(payload.supplier_ids) - valid_ids - missing
    if frozen:
        raise HTTPException(400, "包含冻结供应商,请移除后再提交")

    inquiry = Inquiry(
        code=generate_inquiry_code(session),
        title=payload.title.strip(),
        remark=payload.remark,
        buyer_id=current_user.id,
        delivery_date=payload.delivery_date,
        delivery_address=payload.delivery_address,
        status=InquiryStatus.OPEN,
    )
    session.add(inquiry)
    session.flush()  # 拿到 inquiry.id

    # 物料行
    for idx, it in enumerate(payload.items):
        session.add(InquiryItem(
            inquiry_id=inquiry.id,
            name=it.name.strip(),
            spec=it.spec,
            unit=it.unit or "个",
            qty=it.qty,
            remark=it.remark,
            sort_order=idx,
        ))

    # 邀标 + 自动生成 magic link token
    for sid in payload.supplier_ids:
        if sid in valid_ids:
            session.add(InquiryInvite(
                inquiry_id=inquiry.id,
                supplier_id=sid,
                token=secrets.token_urlsafe(32),
            ))

    session.commit()
    session.refresh(inquiry)
    return _load_detail(inquiry.id, session)


@router.get("", response_model=InquiryListResponse)
def list_inquiries(
    status_filter: InquiryStatus | None = Query(default=None, alias="status"),
    keyword: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
) -> InquiryListResponse:
    stmt = select(Inquiry)
    count_stmt = select(func.count()).select_from(Inquiry)
    filters = []
    if status_filter:
        filters.append(Inquiry.status == status_filter)
    if keyword:
        pattern = f"%{keyword}%"
        from sqlalchemy import or_
        filters.append(or_(Inquiry.title.like(pattern), Inquiry.code.like(pattern)))
    for f in filters:
        stmt = stmt.where(f)
        count_stmt = count_stmt.where(f)
    stmt = stmt.order_by(Inquiry.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    rows = session.exec(stmt).all()
    total = session.exec(count_stmt).one()
    return InquiryListResponse(
        items=[_build_inquiry_read(r, session) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


def _load_detail(inquiry_id: int, session: Session) -> InquiryDetail:
    inquiry = session.get(Inquiry, inquiry_id)
    if not inquiry:
        raise HTTPException(404, "比价单不存在")
    base = _build_inquiry_read(inquiry, session)

    items = session.exec(
        select(InquiryItem).where(InquiryItem.inquiry_id == inquiry_id).order_by(InquiryItem.sort_order, InquiryItem.id)
    ).all()
    invites = session.exec(
        select(InquiryInvite).where(InquiryInvite.inquiry_id == inquiry_id)
    ).all()
    supplier_rows = session.exec(
        select(Supplier).where(Supplier.id.in_([i.supplier_id for i in invites]))
    ).all() if invites else []
    lines = session.exec(
        select(QuoteLine).where(QuoteLine.inquiry_id == inquiry_id)
    ).all()

    return InquiryDetail(
        **base.model_dump(),
        items=[InquiryItemRead.model_validate(i) for i in items],
        suppliers=[SupplierMini.model_validate(s) for s in supplier_rows],
        invites=[InviteRead(supplier_id=v.supplier_id, token=v.token, invited_at=v.invited_at, quoted_at=v.quoted_at) for v in invites],
        quote_lines=[QuoteLineRead.model_validate(q) for q in lines],
    )


@router.get("/{inquiry_id}", response_model=InquiryDetail)
def get_inquiry(
    inquiry_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
) -> InquiryDetail:
    return _load_detail(inquiry_id, session)


@router.patch("/{inquiry_id}", response_model=InquiryDetail)
def update_inquiry(
    inquiry_id: int,
    payload: InquiryUpdate,
    session: Session = Depends(get_session),
    _: User = Depends(require_buyer_or_admin),
) -> InquiryDetail:
    """编辑询价单基本信息(标题/说明/交期/地址)。物料和邀请名单不在此处改。"""
    inquiry = session.get(Inquiry, inquiry_id)
    if not inquiry:
        raise HTTPException(404, "询价单不存在")
    if inquiry.status == InquiryStatus.CLOSED:
        raise HTTPException(400, "已关闭的询价单不可修改")

    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(400, "未提供任何修改内容")

    if "title" in data and data["title"]:
        inquiry.title = data["title"].strip()
    if "remark" in data:
        inquiry.remark = data["remark"]
    if "delivery_date" in data:
        inquiry.delivery_date = data["delivery_date"]
    if "delivery_address" in data:
        inquiry.delivery_address = data["delivery_address"]
    inquiry.updated_at = datetime.now(UTC)

    session.add(inquiry)
    session.commit()
    return _load_detail(inquiry_id, session)


@router.post("/{inquiry_id}/close", response_model=InquiryDetail)
def close_inquiry(
    inquiry_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(require_buyer_or_admin),
) -> InquiryDetail:
    inquiry = session.get(Inquiry, inquiry_id)
    if not inquiry:
        raise HTTPException(404, "比价单不存在")
    if inquiry.status == InquiryStatus.CLOSED:
        raise HTTPException(400, "此单已关闭")
    inquiry.status = InquiryStatus.CLOSED
    inquiry.closed_at = datetime.now(UTC)
    inquiry.updated_at = datetime.now(UTC)
    session.add(inquiry)
    session.commit()
    return _load_detail(inquiry_id, session)


@router.post("/{inquiry_id}/award", response_model=InquiryDetail)
def award_inquiry(
    inquiry_id: int,
    payload: InquiryAwardRequest,
    session: Session = Depends(get_session),
    _: User = Depends(require_buyer_or_admin),
) -> InquiryDetail:
    inquiry = session.get(Inquiry, inquiry_id)
    if not inquiry:
        raise HTTPException(404, "比价单不存在")
    # 必须是被邀请的供应商
    invite = session.exec(
        select(InquiryInvite).where(
            InquiryInvite.inquiry_id == inquiry_id,
            InquiryInvite.supplier_id == payload.supplier_id,
        )
    ).first()
    if not invite:
        raise HTTPException(400, "该供应商不在此比价单邀请列表")
    inquiry.awarded_supplier_id = payload.supplier_id
    inquiry.awarded_note = payload.note
    # 定标即关闭
    if inquiry.status != InquiryStatus.CLOSED:
        inquiry.status = InquiryStatus.CLOSED
        inquiry.closed_at = datetime.now(UTC)
    inquiry.updated_at = datetime.now(UTC)
    session.add(inquiry)
    session.commit()
    return _load_detail(inquiry_id, session)


@router.get("/{inquiry_id}/supplier-quotes", response_model=InquirySupplierQuotesResponse)
def get_supplier_quotes(
    inquiry_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
) -> InquirySupplierQuotesResponse:
    """采购员看每家供应商的完整报价(rows+attachments),方式4混合视图"""
    inquiry = session.get(Inquiry, inquiry_id)
    if not inquiry:
        raise HTTPException(404, "询价单不存在")

    invites = session.exec(
        select(InquiryInvite).where(InquiryInvite.inquiry_id == inquiry_id)
    ).all()
    suppliers_by_id = {
        s.id: s for s in session.exec(
            select(Supplier).where(Supplier.id.in_([i.supplier_id for i in invites]))
        ).all()
    } if invites else {}

    result = []
    for inv in invites:
        sup = suppliers_by_id.get(inv.supplier_id)
        if not sup:
            continue
        # 取该供应商最新 revision 的 rows
        latest_rev = session.exec(
            select(QuoteRevision)
            .where(QuoteRevision.inquiry_id == inquiry_id, QuoteRevision.supplier_id == sup.id)
            .order_by(QuoteRevision.version.desc())
            .limit(1)
        ).first()
        rev_count = session.exec(
            select(func.count()).select_from(QuoteRevision).where(
                QuoteRevision.inquiry_id == inquiry_id,
                QuoteRevision.supplier_id == sup.id,
            )
        ).one()
        if latest_rev:
            rows = session.exec(
                select(QuoteRow)
                .where(QuoteRow.revision_id == latest_rev.id)
                .order_by(QuoteRow.sort_order, QuoteRow.id)
            ).all()
        else:
            rows = []
        atts = session.exec(
            select(QuoteAttachment)
            .where(QuoteAttachment.inquiry_id == inquiry_id, QuoteAttachment.supplier_id == sup.id)
            .order_by(QuoteAttachment.uploaded_at)
        ).all()
        total = Decimal("0")
        for r in rows:
            if r.qty is not None:
                total += r.qty * r.unit_price
            else:
                total += r.unit_price
        result.append(SupplierQuoteDetail(
            supplier_id=sup.id,
            supplier_code=sup.code,
            company_name=sup.company_name,
            contact_phone=sup.contact_phone,
            quoted_at=inv.quoted_at,
            rows=[AdminQuoteRow.model_validate(r) for r in rows],
            attachments=[AdminAttachment.model_validate(a) for a in atts],
            total_amount=total,
            row_count=len(rows),
            revision_count=rev_count,
            current_version=latest_rev.version if latest_rev else None,
        ))

    # 按已报价+总金额排序
    result.sort(key=lambda x: (x.quoted_at is None, x.total_amount))

    return InquirySupplierQuotesResponse(
        inquiry_id=inquiry.id,
        inquiry_code=inquiry.code,
        suppliers=result,
    )


@router.get("/{inquiry_id}/supplier-quotes/{supplier_id}/history", response_model=SupplierHistoryResponse)
def get_supplier_history(
    inquiry_id: int,
    supplier_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
) -> SupplierHistoryResponse:
    """某供应商在此询价单的所有提交版本(调价历史)"""
    inquiry = session.get(Inquiry, inquiry_id)
    if not inquiry:
        raise HTTPException(404, "询价单不存在")
    supplier = session.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(404, "供应商不存在")
    # 确认该供应商确实被邀
    invite = session.exec(
        select(InquiryInvite).where(
            InquiryInvite.inquiry_id == inquiry_id,
            InquiryInvite.supplier_id == supplier_id,
        )
    ).first()
    if not invite:
        raise HTTPException(400, "该供应商未被邀请至此询价单")

    revisions = session.exec(
        select(QuoteRevision)
        .where(QuoteRevision.inquiry_id == inquiry_id, QuoteRevision.supplier_id == supplier_id)
        .order_by(QuoteRevision.version.asc())
    ).all()

    snapshots = []
    for rev in revisions:
        rows = session.exec(
            select(QuoteRow)
            .where(QuoteRow.revision_id == rev.id)
            .order_by(QuoteRow.sort_order, QuoteRow.id)
        ).all()
        snapshots.append(RevisionSnapshot(
            id=rev.id,
            version=rev.version,
            committed_at=rev.committed_at,
            total_amount=rev.total_amount,
            row_count=rev.row_count,
            source_summary=rev.source_summary,
            has_attachment=bool(rev.has_attachment),
            rows=[RevisionRow.model_validate(r) for r in rows],
        ))

    return SupplierHistoryResponse(
        supplier_id=supplier.id,
        supplier_code=supplier.code,
        company_name=supplier.company_name,
        inquiry_id=inquiry.id,
        inquiry_code=inquiry.code,
        revisions=snapshots,
    )


@router.get("/{inquiry_id}/attachment/{attachment_id}/download")
def admin_download_attachment(
    inquiry_id: int,
    attachment_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    """采购员下载供应商上传的附件"""
    att = session.get(QuoteAttachment, attachment_id)
    if not att or att.inquiry_id != inquiry_id:
        raise HTTPException(404, "附件不存在")
    disk_path = UPLOAD_ROOT / att.storage_path
    if not disk_path.exists():
        raise HTTPException(404, "文件已丢失")
    return FileResponse(
        path=str(disk_path),
        filename=att.filename,
        media_type=att.mime_type,
    )


@router.delete("/{inquiry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_inquiry(
    inquiry_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(require_buyer_or_admin),
) -> None:
    """只允许删除尚未有任何报价的比价单"""
    inquiry = session.get(Inquiry, inquiry_id)
    if not inquiry:
        raise HTTPException(404, "比价单不存在")
    has_quote = session.exec(
        select(func.count()).select_from(QuoteLine).where(QuoteLine.inquiry_id == inquiry_id)
    ).one()
    if has_quote:
        raise HTTPException(400, "已有供应商报价,无法删除。可关闭此单。")
    session.delete(inquiry)
    session.commit()


# ============== 供应商端 ==============

# 独立路由组,避免和上面的 /inquiries/{id} 吃到 /inquiries/my 这类字符串
my_router = APIRouter(prefix="/my-inquiries", tags=["inquiries"])


@my_router.get("", response_model=list[InquiryRead])
def my_invited_inquiries(
    status_filter: InquiryStatus | None = Query(default=None, alias="status"),
    session: Session = Depends(get_session),
    sup: Supplier = Depends(get_current_supplier),
) -> list[InquiryRead]:
    """当前供应商被邀请的所有比价单"""
    stmt = (
        select(Inquiry)
        .join(InquiryInvite, InquiryInvite.inquiry_id == Inquiry.id)
        .where(InquiryInvite.supplier_id == sup.id)
    )
    if status_filter:
        stmt = stmt.where(Inquiry.status == status_filter)
    stmt = stmt.order_by(Inquiry.created_at.desc())
    rows = session.exec(stmt).all()
    return [_build_inquiry_read(r, session) for r in rows]


@my_router.get("/{inquiry_id}", response_model=MyInquiryDetail)
def my_inquiry_detail(
    inquiry_id: int,
    session: Session = Depends(get_session),
    sup: Supplier = Depends(get_current_supplier),
) -> MyInquiryDetail:
    """单张比价单详情(含自己已填的价)"""
    inquiry = session.get(Inquiry, inquiry_id)
    if not inquiry:
        raise HTTPException(404, "比价单不存在")
    invite = session.exec(
        select(InquiryInvite).where(
            InquiryInvite.inquiry_id == inquiry_id, InquiryInvite.supplier_id == sup.id
        )
    ).first()
    if not invite:
        raise HTTPException(403, "你未被邀请填写此比价单")

    items = session.exec(
        select(InquiryItem).where(InquiryItem.inquiry_id == inquiry_id).order_by(InquiryItem.sort_order, InquiryItem.id)
    ).all()
    my_lines = session.exec(
        select(QuoteLine).where(QuoteLine.inquiry_id == inquiry_id, QuoteLine.supplier_id == sup.id)
    ).all()
    my_lines_by_item = {line.inquiry_item_id: line for line in my_lines}

    item_views = []
    for it in items:
        line = my_lines_by_item.get(it.id)
        item_views.append(MyInquiryItem(
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

    return MyInquiryDetail(
        id=inquiry.id,
        code=inquiry.code,
        title=inquiry.title,
        remark=inquiry.remark,
        delivery_date=inquiry.delivery_date,
        delivery_address=inquiry.delivery_address,
        status=inquiry.status,
        created_at=inquiry.created_at,
        quoted_at=invite.quoted_at,
        items=item_views,
    )


@my_router.put("/{inquiry_id}/quote", response_model=MyInquiryDetail)
def submit_my_quote(
    inquiry_id: int,
    payload: MyQuoteSubmit,
    session: Session = Depends(get_session),
    sup: Supplier = Depends(get_current_supplier),
) -> MyInquiryDetail:
    """提交/更新当前供应商在此比价单的报价(覆盖式:传什么就是什么)"""
    inquiry = session.get(Inquiry, inquiry_id)
    if not inquiry:
        raise HTTPException(404, "比价单不存在")
    if inquiry.status == InquiryStatus.CLOSED:
        raise HTTPException(400, "此比价单已关闭,无法提交报价")
    invite = session.exec(
        select(InquiryInvite).where(
            InquiryInvite.inquiry_id == inquiry_id, InquiryInvite.supplier_id == sup.id
        )
    ).first()
    if not invite:
        raise HTTPException(403, "你未被邀请填写此比价单")

    # 校验传入的 item_id 都属于该比价单
    items = session.exec(
        select(InquiryItem).where(InquiryItem.inquiry_id == inquiry_id)
    ).all()
    valid_item_ids = {i.id for i in items}
    for line in payload.lines:
        if line.item_id not in valid_item_ids:
            raise HTTPException(400, f"物料行 {line.item_id} 不属于此比价单")

    # Upsert:已有则更新,无则插入
    existing = session.exec(
        select(QuoteLine).where(QuoteLine.inquiry_id == inquiry_id, QuoteLine.supplier_id == sup.id)
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
                inquiry_id=inquiry_id,
                inquiry_item_id=line.item_id,
                supplier_id=sup.id,
                unit_price=line.unit_price,
                note=line.note,
            ))

    # 标记首次提交时间
    if not invite.quoted_at:
        invite.quoted_at = now
        session.add(invite)

    session.commit()
    return my_inquiry_detail(inquiry_id, session, sup)
