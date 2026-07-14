"""Data Center (§7): upload real business data via CSV/XLSX with preview,
column mapping, validation and explicit commit."""

import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pymongo.database import Database

from ..database import get_db
from ..models import Business
from ..security import get_current_business
from ..services.import_engine import SCHEMAS, commit_rows, parse_file, suggest_mapping, validate_rows

router = APIRouter(prefix="/api/data-center", tags=["data-center"])

MAX_FILE_BYTES = 5 * 1024 * 1024


async def _read_upload(file: UploadFile) -> bytes:
    content = await file.read()
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(status_code=400, detail="File too large (max 5 MB)")
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")
    return content


def _check_type(data_type: str) -> None:
    if data_type not in SCHEMAS:
        raise HTTPException(status_code=400,
                            detail=f"Unknown data type '{data_type}'. Supported: {', '.join(SCHEMAS)}")


@router.get("/types")
def data_types():
    """Supported import types with their target fields (for the mapping UI)."""
    return {"types": {
        dtype: [{"field": f, "required": req, "kind": kind} for f, (req, kind) in schema.items()]
        for dtype, schema in SCHEMAS.items()
    }}


@router.post("/preview")
async def preview(data_type: str = Form(...), file: UploadFile = File(...),
                  business: Business = Depends(get_current_business)):
    _check_type(data_type)
    content = await _read_upload(file)
    try:
        df = parse_file(file.filename or "", content)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not parse file: {exc}")
    mapping = suggest_mapping(data_type, list(df.columns))
    sample = df.head(8).to_dict(orient="records")
    return {
        "columns": list(df.columns),
        "row_count": len(df),
        "sample": sample,
        "suggested_mapping": mapping,
        "target_fields": [{"field": f, "required": req, "kind": kind}
                          for f, (req, kind) in SCHEMAS[data_type].items()],
    }


@router.post("/import")
async def import_data(data_type: str = Form(...), mapping: str = Form(...),
                      commit: bool = Form(False), file: UploadFile = File(...),
                      business: Business = Depends(get_current_business),
                      db: Database = Depends(get_db)):
    _check_type(data_type)
    content = await _read_upload(file)
    try:
        df = parse_file(file.filename or "", content)
        mapping_dict = json.loads(mapping)
        if not isinstance(mapping_dict, dict):
            raise ValueError("mapping must be a JSON object")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not parse input: {exc}")

    result = validate_rows(data_type, df, mapping_dict)
    response = {"report": result["report"], "committed": False,
                "data_source": business.data_source}
    if commit and result["rows"]:
        counts = commit_rows(db, business, data_type, result["rows"])
        response.update({"committed": True, **counts, "data_source": business.data_source})
    return response


@router.get("/status")
def import_status(business: Business = Depends(get_current_business), db: Database = Depends(get_db)):
    """What data the twin currently holds and where it came from."""
    def count(collection: str) -> int:
        return db[collection].count_documents({"business_id": business.id})

    products_total = count("products")
    products_demo = db.products.count_documents({"business_id": business.id, "is_demo": 1})
    return {
        "data_source": business.data_source,
        "counts": {
            "products": products_total,
            "demo_products": products_demo,
            "real_products": products_total - products_demo,
            "daily_metrics": count("daily_metrics"),
            "product_sales": count("product_sales"),
            "suppliers": count("suppliers"),
            "employees": count("employees"),
        },
    }
