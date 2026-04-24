"""供应商报价版本化 — quote_revision 表 + quote_row.revision_id

现有 rows 会被 bootstrap 到一个 version=1 的 revision 下。
"""

from alembic import op
import sqlalchemy as sa


revision = "20260424_0008"
down_revision = "20260424_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 建 quote_revision 表
    op.create_table(
        "quote_revision",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("inquiry_id", sa.Integer(), sa.ForeignKey("inquiry.id", ondelete="CASCADE"), nullable=False),
        sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("supplier.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("total_amount", sa.Numeric(16, 2), nullable=False, server_default="0"),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_summary", sa.String(length=32), nullable=False, server_default="manual"),
        sa.Column("has_attachment", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("client_ip", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_qrev_supplier_inquiry", "quote_revision", ["supplier_id", "inquiry_id"])
    op.create_index("ix_qrev_inquiry", "quote_revision", ["inquiry_id"])

    # 2. quote_row 加 revision_id 列(先 nullable)
    op.add_column("quote_row", sa.Column("revision_id", sa.Integer(), nullable=True))

    # 3. 数据迁移:把现有 (inquiry_id, supplier_id) 下的 rows 全部归到一个 version=1 的 revision
    conn = op.get_bind()
    groups = conn.execute(sa.text("""
        SELECT inquiry_id, supplier_id,
               MIN(created_at) as first_at,
               COUNT(*) as cnt,
               COALESCE(SUM(CASE WHEN qty IS NOT NULL THEN qty * unit_price ELSE unit_price END), 0) as total
        FROM quote_row
        WHERE revision_id IS NULL
        GROUP BY inquiry_id, supplier_id
    """)).fetchall()

    for g in groups:
        iid, sid, first_at, cnt, total = g
        res = conn.execute(sa.text("""
            INSERT INTO quote_revision
                (inquiry_id, supplier_id, version, committed_at, total_amount, row_count, source_summary)
            VALUES (:iid, :sid, 1, :at, :total, :cnt, 'bootstrap')
            RETURNING id
        """), {"iid": iid, "sid": sid, "at": first_at, "total": total, "cnt": cnt}).fetchone()
        rev_id = res[0]
        conn.execute(sa.text("""
            UPDATE quote_row SET revision_id = :rid
            WHERE inquiry_id = :iid AND supplier_id = :sid AND revision_id IS NULL
        """), {"rid": rev_id, "iid": iid, "sid": sid})

    # 4. 孤儿 rows (没有对应 revision) 直接删(一般不应存在,兜底)
    conn.execute(sa.text("DELETE FROM quote_row WHERE revision_id IS NULL"))

    # 5. 改 NOT NULL + 加外键 + 加索引
    op.alter_column("quote_row", "revision_id", existing_type=sa.Integer(), nullable=False)
    op.create_foreign_key(
        "fk_qrow_revision",
        "quote_row",
        "quote_revision",
        ["revision_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_qrow_revision", "quote_row", ["revision_id"])


def downgrade() -> None:
    op.drop_index("ix_qrow_revision", table_name="quote_row")
    op.drop_constraint("fk_qrow_revision", "quote_row", type_="foreignkey")
    op.drop_column("quote_row", "revision_id")
    op.drop_index("ix_qrev_inquiry", table_name="quote_revision")
    op.drop_index("ix_qrev_supplier_inquiry", table_name="quote_revision")
    op.drop_table("quote_revision")
