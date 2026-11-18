"""Initial schema for British Auction RFQ System

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-11-18 00:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "rfqs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("reference_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("bid_start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("bid_close_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_close_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("forced_close_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("pickup_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rfqs_reference_id", "rfqs", ["reference_id"], unique=True)

    op.create_table(
        "auction_configs",
        sa.Column("rfq_id", sa.String(), nullable=False),
        sa.Column("trigger_window_minutes", sa.Integer(), nullable=False),
        sa.Column("extension_minutes", sa.Integer(), nullable=False),
        sa.Column("trigger_type", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["rfq_id"], ["rfqs.id"]),
        sa.PrimaryKeyConstraint("rfq_id"),
    )

    op.create_table(
        "bids",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("rfq_id", sa.String(), nullable=False),
        sa.Column("supplier_id", sa.String(), nullable=False),
        sa.Column("supplier_name", sa.String(), nullable=False),
        sa.Column("carrier_name", sa.String(), nullable=False),
        sa.Column("freight_charges", sa.Float(), nullable=False),
        sa.Column("origin_charges", sa.Float(), nullable=False),
        sa.Column("destination_charges", sa.Float(), nullable=False),
        sa.Column("total_price", sa.Float(), nullable=False),
        sa.Column("transit_time_days", sa.Integer(), nullable=False),
        sa.Column("quote_validity", sa.String(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["rfq_id"], ["rfqs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bids_rfq_id", "bids", ["rfq_id"], unique=False)
    op.create_index("ix_bids_supplier_id", "bids", ["supplier_id"], unique=False)
    op.create_index("ix_bids_total_price", "bids", ["total_price"], unique=False)
    op.create_index("ix_bids_submitted_at", "bids", ["submitted_at"], unique=False)

    op.create_table(
        "auction_events",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("rfq_id", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("bid_id", sa.String(), nullable=True),
        sa.Column("old_close_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("new_close_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["bid_id"], ["bids.id"]),
        sa.ForeignKeyConstraint(["rfq_id"], ["rfqs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_auction_events_rfq_id", "auction_events", ["rfq_id"], unique=False)
    op.create_index("ix_auction_events_created_at", "auction_events", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_auction_events_created_at", table_name="auction_events")
    op.drop_index("ix_auction_events_rfq_id", table_name="auction_events")
    op.drop_table("auction_events")
    op.drop_index("ix_bids_submitted_at", table_name="bids")
    op.drop_index("ix_bids_total_price", table_name="bids")
    op.drop_index("ix_bids_supplier_id", table_name="bids")
    op.drop_index("ix_bids_rfq_id", table_name="bids")
    op.drop_table("bids")
    op.drop_table("auction_configs")
    op.drop_index("ix_rfqs_reference_id", table_name="rfqs")
    op.drop_table("rfqs")
