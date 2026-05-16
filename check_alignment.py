from __future__ import annotations

import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
import json


BASE_URL = "http://127.0.0.1:8000"


def get_json(path: str):
    request = Request(f"{BASE_URL}{path}", headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"{path} -> HTTP {exc.code}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"{path} -> cannot connect to {BASE_URL}: {exc.reason}") from exc


def main() -> int:
    checks: list[tuple[str, str]] = []

    try:
        health = get_json("/health")
        assert health.get("status") == "ok"
        checks.append(("PASS", "GET /health"))

        runs = get_json("/runs")
        assert isinstance(runs, list)
        checks.append(("PASS", f"GET /runs ({len(runs)} runs)"))

        latest = get_json("/runs/latest")
        run_id = latest["run_id"]
        checks.append(("PASS", f"GET /runs/latest ({run_id})"))

        summary = get_json(f"/runs/{quote(run_id)}/summary")
        for key in ["vehicle_count", "module_count", "forecast_demand_qty", "weekly_capacity_qty"]:
            assert key in summary
        checks.append(("PASS", "GET /runs/{run_id}/summary"))

        tables = get_json(f"/runs/{quote(run_id)}/tables")
        assert isinstance(tables, list) and tables
        table_name = tables[0]["table_name"]
        checks.append(("PASS", f"GET /runs/{{run_id}}/tables ({len(tables)} tables)"))

        table_rows = get_json(f"/runs/{quote(run_id)}/tables/{quote(table_name)}?page=1&page_size=5")
        assert "rows" in table_rows and "total" in table_rows
        checks.append(("PASS", f"GET /runs/{{run_id}}/tables/{table_name}"))

        material_gap = get_json(f"/runs/{quote(run_id)}/demand-supply-gap?limit=5")
        assert isinstance(material_gap, list)
        checks.append(("PASS", "GET /runs/{run_id}/demand-supply-gap"))

        capacity_gap = get_json(f"/runs/{quote(run_id)}/capacity-gap?limit=5")
        assert isinstance(capacity_gap, list)
        checks.append(("PASS", "GET /runs/{run_id}/capacity-gap"))

    except Exception as exc:
        print(f"FAIL {exc}")
        return 1

    for status, message in checks:
        print(f"{status} {message}")
    print("All backend/frontend-aligned API checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
