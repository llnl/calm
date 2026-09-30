"""SQLAlchemy Core table definitions for the workspace database.

Defines table metadata used by the SQLite workspace storage backend. The
definitions are intentionally explicit and avoid importing ORM-heavy modules
at runtime.
"""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.sql import func

metadata = MetaData()

# NOTE: These are SQLAlchemy Core tables (no ORM).

# -----------------------------------------------------------------------------
# Current project schema marker
# -----------------------------------------------------------------------------

schema_version = Table(
    "schema_version",
    metadata,
    Column("version_id", Integer, primary_key=True, autoincrement=True),
    Column("schema_version", String, nullable=False),
    Column("calm_version", String, nullable=False),
    Column(
        "applied_at", DateTime, nullable=False, server_default=func.current_timestamp()
    ),
    Column("description", Text, nullable=True),
)

bulks = Table(
    "bulks",
    metadata,
    Column("bulk_pk", Integer, primary_key=True, autoincrement=True),
    Column("uid_full", String, nullable=False, unique=True, index=True),
    Column("id_short", String, nullable=False, unique=True, index=True),
    Column("label", String, nullable=True, index=True),
    # Bulk "kind": "reference" (as provided by user) or "optimized" (relaxed).
    Column("kind", String, nullable=False, server_default="reference", index=True),
    # Optional calculator reference for optimized bulks.
    Column(
        "optimized_with_calculator_uid_full",
        String,
        ForeignKey("calculators.uid_full"),
        nullable=True,
        index=True,
    ),
    Column("payload_json", Text, nullable=True),
    Column(
        "created_at", DateTime, nullable=False, server_default=func.current_timestamp()
    ),
    Column(
        "updated_at", DateTime, nullable=False, server_default=func.current_timestamp()
    ),
)


calculators = Table(
    "calculators",
    metadata,
    Column("calculator_pk", Integer, primary_key=True, autoincrement=True),
    # Content-addressed key (see calm.keys.uid.calculator_uid).
    Column("uid_full", String, nullable=False, unique=True, index=True),
    # Human-friendly short ID for interactive UX.
    Column("id_short", String, nullable=False, unique=True, index=True),
    # Compact representation shown in tables: "{family}:{model}".
    Column("family", String, nullable=False, index=True),
    Column("model", String, nullable=False, index=True),
    Column("device", String, nullable=False, server_default="cpu", index=True),
    # Serialized spec JSON for storage and reconstruction
    Column("spec_json", Text, nullable=True),
    Column(
        "created_at", DateTime, nullable=False, server_default=func.current_timestamp()
    ),
    Column(
        "updated_at", DateTime, nullable=False, server_default=func.current_timestamp()
    ),
)

slabs = Table(
    "slabs",
    metadata,
    Column("slab_pk", Integer, primary_key=True, autoincrement=True),
    Column("uid_full", String, nullable=False, unique=True, index=True),
    Column("id_short", String, nullable=False, unique=True, index=True),
    Column("bulk_pk", Integer, ForeignKey("bulks.bulk_pk"), nullable=False, index=True),
    Column("miller_h", Integer, nullable=True, index=True),
    Column("miller_k", Integer, nullable=True, index=True),
    Column("miller_l", Integer, nullable=True, index=True),
    Column("payload_json", Text, nullable=True),
    # Normalized tilt/ shear summary columns for fast querying/ranking.
    Column("tilt_x", Float, nullable=True, index=False),
    Column("tilt_y", Float, nullable=True, index=False),
    Column("tilt_magnitude", Float, nullable=True, index=False),
    Column("has_residual_tilt", Boolean, nullable=True),
    Column("orthogonalize_c_applied", Boolean, nullable=True),
    Column("integer_c_tilt_reduction_applied", Boolean, nullable=True),
    Column("c_tilt_m", Integer, nullable=True),
    Column("c_tilt_n", Integer, nullable=True),
    Column(
        "created_at", DateTime, nullable=False, server_default=func.current_timestamp()
    ),
    Column(
        "updated_at", DateTime, nullable=False, server_default=func.current_timestamp()
    ),
)

# -----------------------------------------------------------------------------
# Milestone 4 foundation: runs + artifacts
# -----------------------------------------------------------------------------

runs = Table(
    "runs",
    metadata,
    Column("run_pk", Integer, primary_key=True, autoincrement=True),
    Column("uid_full", String, nullable=False, unique=True, index=True),
    Column("id_short", String, nullable=False, unique=True, index=True),
    Column("run_type", String, nullable=False, index=True),
    Column("status", String, nullable=False, index=True),
    Column("spec_json", Text, nullable=False),
    Column("error_json", Text, nullable=True),
    Column("progress_json", Text, nullable=True),
    Column(
        "created_at", DateTime, nullable=False, server_default=func.current_timestamp()
    ),
    Column(
        "updated_at", DateTime, nullable=False, server_default=func.current_timestamp()
    ),
)


interface_searches = Table(
    "interface_searches",
    metadata,
    Column("search_pk", Integer, primary_key=True, autoincrement=True),
    Column("name", String, nullable=False, unique=True, index=True),
    Column(
        "search_identity",
        String,
        nullable=False,
        unique=True,
        index=True,
    ),
    Column(
        "run_uid_full",
        String,
        ForeignKey("runs.uid_full", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    ),
    Column(
        "created_at", DateTime, nullable=False, server_default=func.current_timestamp()
    ),
    Column(
        "updated_at", DateTime, nullable=False, server_default=func.current_timestamp()
    ),
)

artifacts = Table(
    "artifacts",
    metadata,
    Column("artifact_pk", Integer, primary_key=True, autoincrement=True),
    Column("uid_full", String, nullable=False, unique=True, index=True),
    Column("id_short", String, nullable=False, unique=True, index=True),
    Column(
        "run_uid_full", String, ForeignKey("runs.uid_full"), nullable=False, index=True
    ),
    Column("kind", String, nullable=False, index=True),
    Column("uri", Text, nullable=False),
    Column("metadata_json", Text, nullable=True),
    Column(
        "created_at", DateTime, nullable=False, server_default=func.current_timestamp()
    ),
    Column(
        "updated_at", DateTime, nullable=False, server_default=func.current_timestamp()
    ),
)


prototypes = Table(
    "prototypes",
    metadata,
    Column("prototype_pk", Integer, primary_key=True, autoincrement=True),
    Column("uid_full", String, nullable=False, unique=True, index=True),
    Column("id_short", String, nullable=False, unique=True, index=True),
    Column(
        "run_uid_full", String, ForeignKey("runs.uid_full"), nullable=False, index=True
    ),
    Column(
        "slab_a_uid_full",
        String,
        ForeignKey("slabs.uid_full"),
        nullable=False,
        index=True,
    ),
    Column(
        "slab_b_uid_full",
        String,
        ForeignKey("slabs.uid_full"),
        nullable=False,
        index=True,
    ),
    Column("match_score", Float, nullable=True),
    Column("hencky_norm", Float, nullable=True),
    Column("interface_area", Float, nullable=True),
    Column("n_atoms", Integer, nullable=True),
    Column("is_pareto", Boolean, nullable=False, server_default="0"),
    Column("pareto_rank", Integer, nullable=True),
    Column("payload_json", Text, nullable=True),
    Column(
        "created_at", DateTime, nullable=False, server_default=func.current_timestamp()
    ),
    Column(
        "updated_at", DateTime, nullable=False, server_default=func.current_timestamp()
    ),
)


derived_interfaces = Table(
    "derived_interfaces",
    metadata,
    Column("interface_pk", Integer, primary_key=True, autoincrement=True),
    Column("uid_full", String, nullable=False, unique=True, index=True),
    Column("id_short", String, nullable=False, unique=True, index=True),
    Column(
        "prototype_uid_full",
        String,
        ForeignKey("prototypes.uid_full", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("label", String, nullable=True, index=True),
    # Spec-only representation used to reconstruct an instantiated interface on demand.
    Column("spec_json", Text, nullable=False),
    Column(
        "created_at", DateTime, nullable=False, server_default=func.current_timestamp()
    ),
    Column(
        "updated_at", DateTime, nullable=False, server_default=func.current_timestamp()
    ),
)

# Follow-up analysis result summaries (UX layer)
#
# These records are intentionally lightweight and queryable. Larger payloads
# should live as artifacts (JSON/plots), referenced via the artifacts table.
followup_results = Table(
    "followup_results",
    metadata,
    Column("followup_pk", Integer, primary_key=True),
    Column("uid_full", String, unique=True, nullable=False, index=True),
    Column("id_short", String, unique=True, nullable=False, index=True),
    Column(
        "run_uid_full",
        String,
        ForeignKey("runs.uid_full", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column(
        "prototype_uid_full",
        String,
        ForeignKey("prototypes.uid_full", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    # Optional original seed target. Every follow-up retains its canonical
    # prototype FK above; derived-interface seeds are recorded explicitly here.
    Column("target_uid_full", String, nullable=True, index=True),
    Column("target_kind", String, nullable=True, index=True),
    Column("kind", String, nullable=False, index=True),
    Column("best_energy", Float, nullable=True),
    Column("param1", Float, nullable=True),
    Column("param2", Float, nullable=True),
    Column("n_points", Integer, nullable=True),
    Column("payload_json", Text, nullable=False),
    Column(
        "created_at", DateTime, nullable=False, server_default=func.current_timestamp()
    ),
)


# -----------------------------------------------------------------------------
# Provenance / graph traversal
# -----------------------------------------------------------------------------

edges = Table(
    "edges",
    metadata,
    Column("edge_pk", Integer, primary_key=True, autoincrement=True),
    Column("src_uid_full", String, nullable=False, index=True),
    Column("dst_uid_full", String, nullable=False, index=True),
    Column("kind", String, nullable=False, index=True),
    Column("payload_json", Text, nullable=False),
    # Exact hash of canonical payload JSON. Current repository reads require
    # this value even though the unchanged v1.2.0 SQL column remains nullable.
    Column("payload_hash", String, nullable=True, index=True),
    Column(
        "created_at",
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        index=True,
    ),
    UniqueConstraint(
        "src_uid_full",
        "dst_uid_full",
        "kind",
        "payload_hash",
        name="uq_edges_src_dst_kind_payload",
    ),
)


# -----------------------------------------------------------------------------
# Dataset & Campaign tables (AR-M9.1)
# -----------------------------------------------------------------------------

datasets = Table(
    "datasets",
    metadata,
    Column("dataset_pk", Integer, primary_key=True, autoincrement=True),
    Column("uid_full", String, nullable=False, unique=True, index=True),
    Column("id_short", String, nullable=False, unique=True, index=True),
    Column("project_id", String, nullable=True, index=True),
    Column("name", String, nullable=True, index=True),
    Column("description", Text, nullable=True),
    Column("metadata_json", Text, nullable=True),
    Column(
        "created_at", DateTime, nullable=False, server_default=func.current_timestamp()
    ),
    Column(
        "updated_at", DateTime, nullable=False, server_default=func.current_timestamp()
    ),
)

dataset_items = Table(
    "dataset_items",
    metadata,
    Column("item_pk", Integer, primary_key=True, autoincrement=True),
    Column("uid_full", String, nullable=False, unique=True, index=True),
    Column("id_short", String, nullable=False, unique=True, index=True),
    Column(
        "dataset_uid_full",
        String,
        ForeignKey("datasets.uid_full", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    # 'index' is a SQL keyword; use 'dataset_index' as the column name instead.
    Column("dataset_index", Integer, nullable=True, index=True),
    Column("metadata_json", Text, nullable=True),
    Column("artifact_refs_json", Text, nullable=True),
    Column(
        "created_at", DateTime, nullable=False, server_default=func.current_timestamp()
    ),
)

campaigns = Table(
    "campaigns",
    metadata,
    Column("campaign_pk", Integer, primary_key=True, autoincrement=True),
    Column("uid_full", String, nullable=False, unique=True, index=True),
    Column("id_short", String, nullable=False, unique=True, index=True),
    Column("project_id", String, nullable=True, index=True),
    Column("name", String, nullable=True, index=True),
    Column("spec_json", Text, nullable=True),
    Column(
        "created_at", DateTime, nullable=False, server_default=func.current_timestamp()
    ),
    Column(
        "updated_at", DateTime, nullable=False, server_default=func.current_timestamp()
    ),
)


# -----------------------------------------------------------------------------
# Project-wide authoritative configuration table
# -----------------------------------------------------------------------------
project_configuration = Table(
    "project_configuration",
    metadata,
    Column("config_pk", Integer, primary_key=True, autoincrement=True),
    # Single-row table per workspace DB. Nullable fields represent settings
    # that have not yet been assigned in the current project.
    Column("default_mlip", String, nullable=True),
    Column(
        "default_calculator_uid_full",
        String,
        ForeignKey("calculators.uid_full"),
        nullable=True,
    ),
    Column("workflow_defaults_json", Text, nullable=True),
    Column(
        "created_at", DateTime, nullable=False, server_default=func.current_timestamp()
    ),
    Column(
        "updated_at", DateTime, nullable=False, server_default=func.current_timestamp()
    ),
)

campaign_runs = Table(
    "campaign_runs",
    metadata,
    Column("campaign_run_pk", Integer, primary_key=True, autoincrement=True),
    Column("uid_full", String, nullable=False, unique=True, index=True),
    Column("id_short", String, nullable=False, unique=True, index=True),
    Column(
        "campaign_uid_full",
        String,
        ForeignKey("campaigns.uid_full", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("run_spec_hash", String, nullable=True, index=True),
    Column("backend_id", String, nullable=True, index=True),
    Column("status", String, nullable=True, index=True),
    Column("started_at", DateTime, nullable=True),
    Column("finished_at", DateTime, nullable=True),
    UniqueConstraint(
        "campaign_uid_full",
        "run_spec_hash",
        "backend_id",
        name="uq_campaign_runs_campaign_spec_backend",
    ),
)
