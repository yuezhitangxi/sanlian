from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from .db import ensure_metadata_tables
from .generator_bridge import load_generator_module
from .ontology_mapping import get_ontology_class_record_specs, get_table_field_mapping


def _module() -> Any:
    return load_generator_module()


def allowed_data_tables() -> list[str]:
    module = _module()
    generator = module.ThreeChainMockGenerator(module.CONFIG, module.TODAY)
    world = generator.generate()
    return list(world.__dict__.keys())


def _assert_table_allowed(table_name: str) -> None:
    if table_name not in allowed_data_tables():
        raise ValueError(f"Unsupported table: {table_name}")


def ontology_table_field_mapping() -> dict[str, Any]:
    return get_table_field_mapping()


def list_ontology_classes(engine: Engine, run_id: str | None = None) -> list[dict[str, Any]]:
    specs = get_ontology_class_record_specs()
    resolved_run_id = resolve_run_id(engine, run_id) if run_id is not None else None
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    result = []
    for ontology_class, spec in specs.items():
        table_name = spec.get("source_table")
        filters = spec.get("filters") or {}
        has_table = bool(table_name and table_name in existing_tables)
        row_count = None
        if resolved_run_id is not None and has_table:
            where_parts = ["run_id = :run_id"]
            params: dict[str, Any] = {"run_id": resolved_run_id}
            for idx, (field, value) in enumerate(filters.items()):
                param_name = f"filter_{idx}"
                where_parts.append(f"`{field}` = :{param_name}")
                params[param_name] = value
            sql = text(f"SELECT COUNT(*) FROM `{table_name}` WHERE {' AND '.join(where_parts)}")
            with engine.connect() as conn:
                row_count = int(conn.execute(sql, params).scalar_one())

        result.append(
            {
                "ontology_class": ontology_class,
                "ontology_domain": spec["ontology_domain"],
                "source_table": table_name,
                "filters": filters,
                "has_table": has_table,
                "row_count": row_count,
                "run_id": resolved_run_id,
                "description": spec["description"],
            }
        )
    return result


def ontology_class_records(
    engine: Engine,
    run_id: str,
    ontology_class: str,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    resolved_run_id = resolve_run_id(engine, run_id)
    specs = get_ontology_class_record_specs()
    if ontology_class not in specs:
        raise ValueError(
            f"Unsupported ontology_class: {ontology_class}. Call GET /ontology/classes to see supported classes."
        )

    spec = specs[ontology_class]
    table_name = spec.get("source_table")
    filters = spec.get("filters") or {}
    page = max(page, 1)
    page_size = min(max(page_size, 1), 500)
    offset = (page - 1) * page_size

    if table_name is None:
        return {
            "run_id": resolved_run_id,
            "requested_run_id": run_id,
            "ontology_class": ontology_class,
            "ontology_domain": spec["ontology_domain"],
            "source_table": None,
            "filters": filters,
            "page": page,
            "page_size": page_size,
            "total": 0,
            "records": [],
            "description": spec["description"],
            "data_status": "not_instantiated",
        }

    inspector = inspect(engine)
    if table_name not in inspector.get_table_names():
        return {
            "run_id": resolved_run_id,
            "requested_run_id": run_id,
            "ontology_class": ontology_class,
            "ontology_domain": spec["ontology_domain"],
            "source_table": table_name,
            "filters": filters,
            "page": page,
            "page_size": page_size,
            "total": 0,
            "records": [],
            "description": spec["description"],
            "data_status": "source_table_missing",
        }

    where_parts = ["run_id = :run_id"]
    params: dict[str, Any] = {"run_id": resolved_run_id, "limit": page_size, "offset": offset}
    for idx, (field, value) in enumerate(filters.items()):
        param_name = f"filter_{idx}"
        where_parts.append(f"`{field}` = :{param_name}")
        params[param_name] = value
    where_sql = " AND ".join(where_parts)

    with engine.connect() as conn:
        total = int(
            conn.execute(
                text(f"SELECT COUNT(*) FROM `{table_name}` WHERE {where_sql}"),
                {k: v for k, v in params.items() if k not in {"limit", "offset"}},
            ).scalar_one()
        )
        rows = conn.execute(
            text(f"SELECT * FROM `{table_name}` WHERE {where_sql} LIMIT :limit OFFSET :offset"),
            params,
        ).mappings().all()

    return {
        "run_id": resolved_run_id,
        "requested_run_id": run_id,
        "ontology_class": ontology_class,
        "ontology_domain": spec["ontology_domain"],
        "source_table": table_name,
        "filters": filters,
        "page": page,
        "page_size": page_size,
        "total": total,
        "records": [dict(row) for row in rows],
        "description": spec["description"],
        "data_status": "ok" if total > 0 else "empty",
    }


def assert_run_exists(engine: Engine, run_id: str) -> None:
    ensure_metadata_tables(engine)
    with engine.connect() as conn:
        exists = conn.execute(
            text("SELECT COUNT(*) FROM simulation_run WHERE run_id = :run_id AND status = 'SUCCESS'"),
            {"run_id": run_id},
        ).scalar_one()
    if not exists:
        raise ValueError(
            f"Unknown successful run_id: {run_id}. Call GET /runs and use one of the returned SUCCESS run_id values."
        )


def latest_success_run_id(engine: Engine) -> str:
    ensure_metadata_tables(engine)
    with engine.connect() as conn:
        run_id = conn.execute(
            text(
                """
                SELECT run_id
                FROM simulation_run
                WHERE status = 'SUCCESS'
                ORDER BY generated_at DESC
                LIMIT 1
                """
            )
        ).scalar()
    if not run_id:
        raise ValueError("No successful run exists. Call POST /runs/generate first.")
    return str(run_id)


def latest_run(engine: Engine) -> dict[str, Any]:
    run_id = latest_success_run_id(engine)
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT run_id, run_name, generated_at, output_dir, seed, status, error_message
                FROM simulation_run
                WHERE run_id = :run_id
                """
            ),
            {"run_id": run_id},
        ).mappings().one()
    return dict(row)


def resolve_run_id(engine: Engine, run_id: str | None) -> str:
    if run_id is None or run_id == "latest":
        return latest_success_run_id(engine)
    assert_run_exists(engine, run_id)
    return run_id


def generate_run(engine: Engine, run_name: str | None = None, seed: int | None = None) -> dict[str, Any]:
    module = _module()
    ensure_metadata_tables(engine)

    effective_seed = seed if seed is not None else module.SEED
    output_dir = module.timestamped_output_dir(module.OUTPUT_DIR)
    run_id = output_dir.name

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO simulation_run
                    (run_id, run_name, generated_at, output_dir, seed, status, error_message)
                VALUES
                    (:run_id, :run_name, :generated_at, :output_dir, :seed, 'RUNNING', NULL)
                """
            ),
            {
                "run_id": run_id,
                "run_name": run_name,
                "generated_at": datetime.now(),
                "output_dir": str(output_dir.resolve()),
                "seed": effective_seed,
            },
        )

    try:
        generator = module.ThreeChainMockGenerator(module.CONFIG, module.TODAY, seed=effective_seed)
        world = generator.generate()
        export_result = generator.export(world, output_dir, export_excel=True)

        for table_name, df in world.__dict__.items():
            out_df = df.copy()
            out_df.insert(0, "run_id", run_id)
            out_df.to_sql(table_name, con=engine, if_exists="append", index=False)
        tables = [
            {"table_name": table_name, "row_count": int(len(df))}
            for table_name, df in world.__dict__.items()
        ]

        with engine.begin() as conn:
            conn.execute(
                text("UPDATE simulation_run SET status = 'SUCCESS' WHERE run_id = :run_id"),
                {"run_id": run_id},
            )

        return {
            "run_id": run_id,
            "run_name": run_name,
            "status": "SUCCESS",
            "output_dir": str(output_dir.resolve()),
            "excel_exported": export_result["excel_exported"],
            "excel_path": str(export_result["excel_path"]) if export_result["excel_path"] else None,
            "table_count": len(tables),
            "tables": tables,
            "summary": {
                "vehicle_count": int(len(world.vehicle)),
                "module_count": int(len(world.module)),
                "forecast_demand_qty": float(
                    world.demand.loc[world.demand["demand_type"] == "FORECAST", "quantity"].sum()
                ),
                "order_demand_qty": float(
                    world.demand.loc[world.demand["demand_type"] == "ORDER", "quantity"].sum()
                ),
                "material_need_qty": float(world.fact_material_need_week["need_qty"].sum()),
                "on_hand_qty": float(world.fact_inventory_snapshot["snapshot_qty"].sum()),
                "inbound_qty": float(world.fact_inbound_eta["quantity"].sum()),
                "weekly_capacity_qty": float(world.fact_capacity_week["weekly_capacity_qty"].sum()),
            },
        }
    except Exception as exc:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE simulation_run
                    SET status = 'FAILED', error_message = :error_message
                    WHERE run_id = :run_id
                    """
                ),
                {"run_id": run_id, "error_message": str(exc)},
            )
        raise


def list_runs(engine: Engine) -> list[dict[str, Any]]:
    ensure_metadata_tables(engine)
    query = """
    SELECT run_id, run_name, generated_at, output_dir, seed, status, error_message
    FROM simulation_run
    ORDER BY generated_at DESC
    """
    return pd.read_sql(query, engine).to_dict(orient="records")


def list_tables(engine: Engine, run_id: str) -> list[dict[str, Any]]:
    assert_run_exists(engine, run_id)
    tables = []
    inspector = inspect(engine)
    existing = set(inspector.get_table_names())
    for table_name in allowed_data_tables():
        if table_name not in existing:
            continue
        count_query = text(f"SELECT COUNT(*) AS row_count FROM `{table_name}` WHERE run_id = :run_id")
        with engine.connect() as conn:
            row_count = conn.execute(count_query, {"run_id": run_id}).scalar_one()
        tables.append({"table_name": table_name, "row_count": row_count})
    return tables


def read_table(engine: Engine, run_id: str, table_name: str, page: int, page_size: int) -> dict[str, Any]:
    assert_run_exists(engine, run_id)
    _assert_table_allowed(table_name)
    page = max(page, 1)
    page_size = min(max(page_size, 1), 500)
    offset = (page - 1) * page_size

    with engine.connect() as conn:
        total = conn.execute(
            text(f"SELECT COUNT(*) FROM `{table_name}` WHERE run_id = :run_id"),
            {"run_id": run_id},
        ).scalar_one()
        rows = conn.execute(
            text(f"SELECT * FROM `{table_name}` WHERE run_id = :run_id LIMIT :limit OFFSET :offset"),
            {"run_id": run_id, "limit": page_size, "offset": offset},
        ).mappings().all()

    return {
        "table_name": table_name,
        "page": page,
        "page_size": page_size,
        "total": total,
        "rows": [dict(row) for row in rows],
    }


def summary(engine: Engine, run_id: str) -> dict[str, Any]:
    assert_run_exists(engine, run_id)

    def scalar(sql: str) -> float:
        with engine.connect() as conn:
            value = conn.execute(text(sql), {"run_id": run_id}).scalar()
        return float(value or 0)

    return {
        "run_id": run_id,
        "vehicle_count": int(scalar("SELECT COUNT(*) FROM vehicle WHERE run_id = :run_id")),
        "module_count": int(scalar("SELECT COUNT(*) FROM module WHERE run_id = :run_id")),
        "forecast_demand_qty": scalar(
            "SELECT SUM(quantity) FROM demand WHERE run_id = :run_id AND demand_type = 'FORECAST'"
        ),
        "order_demand_qty": scalar(
            "SELECT SUM(quantity) FROM demand WHERE run_id = :run_id AND demand_type = 'ORDER'"
        ),
        "material_need_qty": scalar("SELECT SUM(need_qty) FROM fact_material_need_week WHERE run_id = :run_id"),
        "on_hand_qty": scalar("SELECT SUM(snapshot_qty) FROM fact_inventory_snapshot WHERE run_id = :run_id"),
        "inbound_qty": scalar("SELECT SUM(quantity) FROM fact_inbound_eta WHERE run_id = :run_id"),
        "weekly_capacity_qty": scalar("SELECT SUM(weekly_capacity_qty) FROM fact_capacity_week WHERE run_id = :run_id"),
    }


def demand_supply_gap(engine: Engine, run_id: str, limit: int = 100) -> list[dict[str, Any]]:
    assert_run_exists(engine, run_id)
    sql = """
    WITH need AS (
        SELECT module_id, week_start, SUM(need_qty) AS need_qty
        FROM fact_material_need_week
        WHERE run_id = :run_id
        GROUP BY module_id, week_start
    ),
    inv AS (
        SELECT module_id, SUM(snapshot_qty) AS inventory_qty
        FROM fact_inventory_snapshot
        WHERE run_id = :run_id
        GROUP BY module_id
    ),
    inbound AS (
        SELECT object_ref_id AS module_id, eta_date AS week_start, SUM(quantity) AS inbound_qty
        FROM fact_inbound_eta
        WHERE run_id = :run_id AND object_type = 'Module'
        GROUP BY object_ref_id, eta_date
    )
    SELECT
        n.module_id,
        n.week_start,
        n.need_qty,
        COALESCE(i.inventory_qty, 0) AS inventory_qty,
        COALESCE(SUM(b.inbound_qty), 0) AS inbound_qty,
        n.need_qty - COALESCE(i.inventory_qty, 0) - COALESCE(SUM(b.inbound_qty), 0) AS gap_qty
    FROM need n
    LEFT JOIN inv i ON i.module_id = n.module_id
    LEFT JOIN inbound b ON b.module_id = n.module_id AND b.week_start <= n.week_start
    GROUP BY n.module_id, n.week_start, n.need_qty, i.inventory_qty
    ORDER BY gap_qty DESC
    LIMIT :limit
    """
    df = pd.read_sql(text(sql), engine, params={"run_id": run_id, "limit": limit})
    df["risk_level"] = df["gap_qty"].apply(lambda x: "HIGH" if x > 0 else "LOW")
    return df.to_dict(orient="records")


def capacity_gap(engine: Engine, run_id: str, limit: int = 100) -> list[dict[str, Any]]:
    assert_run_exists(engine, run_id)
    sql = """
    WITH demand_week AS (
        SELECT vehicle_id, week_start, SUM(qty) AS demand_qty
        FROM fact_demand_week
        WHERE run_id = :run_id
        GROUP BY vehicle_id, week_start
    ),
    capacity_week AS (
        SELECT target_ref_id AS vehicle_id, plant_node_id, week_start, SUM(weekly_capacity_qty) AS capacity_qty
        FROM fact_capacity_week
        WHERE run_id = :run_id AND target_object_type = 'Vehicle'
        GROUP BY target_ref_id, plant_node_id, week_start
    )
    SELECT
        d.vehicle_id,
        c.plant_node_id,
        d.week_start,
        d.demand_qty,
        COALESCE(c.capacity_qty, 0) AS capacity_qty,
        d.demand_qty - COALESCE(c.capacity_qty, 0) AS gap_qty
    FROM demand_week d
    LEFT JOIN capacity_week c ON c.vehicle_id = d.vehicle_id AND c.week_start = d.week_start
    ORDER BY gap_qty DESC
    LIMIT :limit
    """
    df = pd.read_sql(text(sql), engine, params={"run_id": run_id, "limit": limit})
    df["risk_level"] = df["gap_qty"].apply(lambda x: "HIGH" if x > 0 else "LOW")
    return df.to_dict(orient="records")
