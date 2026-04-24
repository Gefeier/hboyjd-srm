"""inquiry_invite 加 token 列 (magic link 填报)"""

import secrets

from alembic import op
import sqlalchemy as sa


revision = "20260424_0005"
down_revision = "20260424_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 先加 nullable 列
    op.add_column(
        "inquiry_invite",
        sa.Column("token", sa.String(length=64), nullable=True),
    )
    # 2. 给历史数据回填 token(每行一个新随机)
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id FROM inquiry_invite WHERE token IS NULL")).fetchall()
    for row in rows:
        conn.execute(
            sa.text("UPDATE inquiry_invite SET token = :tk WHERE id = :id"),
            {"tk": secrets.token_urlsafe(32), "id": row[0]},
        )
    # 3. 改成 NOT NULL + UNIQUE 索引
    op.alter_column("inquiry_invite", "token", nullable=False)
    op.create_index("ix_invite_token", "inquiry_invite", ["token"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_invite_token", table_name="inquiry_invite")
    op.drop_column("inquiry_invite", "token")
