from sqlalchemy import text
from sqlalchemy.orm import Session


TABLES = {
    "supplier", "farm", "slaughterhouse", "wholesaler", "retail",
    "halal_certificate", "vehicle", "slaughterman", "flock",
    "slaughter_batch", "product", "shipment", "inspection",
    "farm_supplier", "batch_flock_source", "shipment_item",
    "wholesaler_retail_contract", "rph_wholesaler_contract", "retail_stock",
}


class SupplyChainRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_rows(self, table: str, limit: int, offset: int) -> list[dict]:
        if table not in TABLES:
            raise ValueError(f"Tabel tidak diizinkan: {table}")
        statement = text(f"SELECT * FROM `{table}` LIMIT :limit OFFSET :offset")
        result = self.db.execute(statement, {"limit": limit, "offset": offset})
        return [dict(row) for row in result.mappings()]

    def count_rows(self, table: str) -> int:
        if table not in TABLES:
            raise ValueError(f"Tabel tidak diizinkan: {table}")
        result = self.db.execute(text(f"SELECT COUNT(*) AS total FROM `{table}`"))
        return int(result.scalar_one())
