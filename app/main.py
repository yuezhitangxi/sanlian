from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .db import get_engine
from .services import (
    capacity_gap,
    demand_supply_gap,
    generate_run,
    latest_run,
    list_ontology_classes,
    list_runs,
    list_tables,
    ontology_class_records,
    ontology_table_field_mapping,
    read_table,
    summary,
)


app = FastAPI(title="Three Chain Simulation Demo API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
engine = get_engine()
FRONTEND_PATH = Path(__file__).resolve().parents[1] / "frontend.html"


class GenerateRunRequest(BaseModel):
    run_name: str | None = None
    seed: int | None = None


@app.get("/", include_in_schema=False)
def frontend_home() -> FileResponse:
    return FileResponse(FRONTEND_PATH, headers={"Cache-Control": "no-store"})


@app.get("/frontend", include_in_schema=False)
def frontend() -> FileResponse:
    return FileResponse(FRONTEND_PATH, headers={"Cache-Control": "no-store"})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ontology/table-field-mapping")
def get_ontology_table_field_mapping() -> dict[str, Any]:
    return ontology_table_field_mapping()


@app.get("/ontology/classes")
def get_ontology_classes(run_id: str | None = None) -> list[dict[str, Any]]:
    try:
        return list_ontology_classes(engine, run_id=run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/ontology/classes/{ontology_class}/records")
def get_latest_ontology_class_records(
    ontology_class: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    try:
        return ontology_class_records(engine, "latest", ontology_class, page, page_size)
    except ValueError as exc:
        message = str(exc)
        status_code = 404 if message.startswith("No successful run") else 400
        raise HTTPException(status_code=status_code, detail=message) from exc


@app.get("/runs/{run_id}/ontology/classes/{ontology_class}/records")
def get_ontology_class_records(
    run_id: str,
    ontology_class: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    try:
        return ontology_class_records(engine, run_id, ontology_class, page, page_size)
    except ValueError as exc:
        message = str(exc)
        status_code = 404 if message.startswith("Unknown successful run_id") else 400
        raise HTTPException(status_code=status_code, detail=message) from exc


@app.get("/runs")
def get_runs() -> list[dict[str, Any]]:
    return list_runs(engine)


@app.get("/runs/latest")
def get_latest_run() -> dict[str, Any]:
    try:
        return latest_run(engine)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/runs/generate")
def post_generate_run(payload: GenerateRunRequest) -> dict[str, Any]:
    try:
        return generate_run(engine, run_name=payload.run_name, seed=payload.seed)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/runs/{run_id}/tables")
def get_tables(run_id: str) -> list[dict[str, Any]]:
    try:
        return list_tables(engine, run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/runs/{run_id}/tables/{table_name}")
def get_table_rows(
    run_id: str,
    table_name: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
) -> dict[str, Any]:
    try:
        return read_table(engine, run_id, table_name, page, page_size)
    except ValueError as exc:
        message = str(exc)
        status_code = 404 if message.startswith("Unknown successful run_id") else 400
        raise HTTPException(status_code=status_code, detail=message) from exc


@app.get("/runs/{run_id}/summary")
def get_summary(run_id: str) -> dict[str, Any]:
    try:
        return summary(engine, run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/runs/{run_id}/demand-supply-gap")
def get_demand_supply_gap(
    run_id: str,
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[dict[str, Any]]:
    try:
        return demand_supply_gap(engine, run_id, limit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/runs/{run_id}/capacity-gap")
def get_capacity_gap(
    run_id: str,
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[dict[str, Any]]:
    try:
        return capacity_gap(engine, run_id, limit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
