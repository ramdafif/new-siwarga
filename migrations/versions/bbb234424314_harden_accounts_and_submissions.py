"""Account audit, session revocation and idempotent complaint submission."""
from alembic import op
import sqlalchemy as sa

revision = "bbb234424314"
down_revision = "aaa123313203"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("session_version", sa.Integer(), server_default="1", nullable=False))
    op.add_column("pengaduan", sa.Column("submission_token", sa.String(64), nullable=True))
    op.create_unique_constraint("uq_pengaduan_submission", "pengaduan", ["pelapor_id", "submission_token"])
    op.create_table("audit_event",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("target_id", sa.Integer(), nullable=True),
        sa.Column("event", sa.String(60), nullable=False),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("request_id", sa.String(32), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False))
    op.create_index("ix_audit_event_created_at", "audit_event", ["created_at"])


def downgrade():
    op.drop_table("audit_event")
    op.drop_constraint("uq_pengaduan_submission", "pengaduan", type_="unique")
    op.drop_column("pengaduan", "submission_token")
    op.drop_column("users", "session_version")
