from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.db.connection import check_database_connection, get_db
from backend.db.repository import SupplyChainRepository, TABLES


router = APIRouter(prefix="/api/v1/database", tags=["Supply Chain Database"])


@router.get("/health")
def database_health():
    try:
        check_database_connection()
    except SQLAlchemyError as exc:
        raise HTTPException(503, "Database supply tidak dapat diakses.") from exc
    return {"status": "connected", "database": "supply"}


@router.get("/tables")
def database_tables():
    return {"tables": sorted(TABLES), "total": len(TABLES)}


@router.get("/{table}")
def list_table_rows(
    table: str,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    if table not in TABLES:
        raise HTTPException(404, f"Tabel '{table}' tidak tersedia di API.")
    repository = SupplyChainRepository(db)
    try:
        rows = repository.list_rows(table, limit, offset)
        total = repository.count_rows(table)
    except SQLAlchemyError as exc:
        raise HTTPException(503, "Query database gagal.") from exc
    return {"table": table, "total": total, "limit": limit, "offset": offset, "data": rows}
