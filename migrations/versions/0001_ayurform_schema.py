"""create AyurForm structured schema"""
from alembic import op
import sqlalchemy as sa

revision = "0001_ayurform_schema"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Use SQLAlchemy metadata so constraints/indexes stay in sync with models.
    from ayurform_sqlalchemy import Base
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)

def downgrade():
    from ayurform_sqlalchemy import Base
    Base.metadata.drop_all(bind=op.get_bind())
