# app/services/hub_service.py
from datetime import datetime, timezone
from typing import Optional, List, Dict
from pymongo.errors import DuplicateKeyError
from app.db.mongodb import db
from app.core.config import COLLECTION_HUBS, COLLECTION_CLOSED_HUBS
from app.models.hub import RegisterHub, UpdateHub, HubOut, ClosedHub
from app.utiles.logger import get_logger

 
logger = get_logger(__name__)
 
# --------------------------
# Helper functions
# --------------------------
def _now_utc():
    """Return current UTC datetime."""
    return datetime.now(timezone.utc)
 
def _normalize_hub_id(hub_id: str):
    """Format hub_id → strip spaces + uppercase."""
    return hub_id.strip().upper()
 
def _normalize_hub_name(hub_name: str):
    """Format hub_name → strip spaces."""
    return hub_name.strip()
 
# --------------------------
# Create hub
# --------------------------
async def create_hub(payload: RegisterHub) -> Dict:
    """Register a new hub in MongoDB."""
    hub_id = _normalize_hub_id(payload.hub_id)
    hub_name = _normalize_hub_name(payload.hub_name)

    # Prepare hub document
    doc = {
        "hub_id": hub_id,
        "hub_name": hub_name,
        "hub_manager": payload.hub_manager,
        "hub_phone_number": payload.hub_phone_number,
        "hub_address": payload.hub_address,
        "status": "Active",
        "hub_opening_date": _now_utc(),
        "created_at": _now_utc(),
        "updated_at": None
    }

    # Validate hub_manager is not already assigned to another active hub
    if payload.hub_manager:
        existing = await db[COLLECTION_HUBS].find_one({"hub_manager": payload.hub_manager, "status": "Active"})
        if existing:
            logger.error(
                f"Manager '{payload.hub_manager}' already assigned to another active hub (hub_id={existing.get('hub_id')})"
            )
            raise ValueError(
                f"Manager '{payload.hub_manager}' already assigned to another active hub (hub_id={existing.get('hub_id')})"
            )

    # Insert hub document
    try:
        logger.info("Inserting hub into MongoDB: %s", doc)
        result = await db[COLLECTION_HUBS].insert_one(doc)
        logger.info("✅ Insert result: %s", result.inserted_id)

    except DuplicateKeyError as e:
        # Convert DB duplicate error into user-friendly error
        logger.exception("Duplicate on create_hub for hub_id=%s, hub_name=%s", hub_id, hub_name)
        raise ValueError("hub_id or hub_name already exists") from e
 
    return {"message": "Hub created successfully", "hub_id": hub_id, "hub_name": hub_name}
 
 
# --------------------------
# Update hub
# --------------------------
async def update_hub(hub_id: str, payload: UpdateHub) -> Dict:
    """Update hub details (hub_manager, status, etc.)."""
    hub_id_norm = _normalize_hub_id(hub_id)

    # Filter only non-null fields for update
    update_fields = {k: v for k, v in payload.dict().items() if v is not None}
    if not update_fields:
        logger.error("No field (other than hub_id) must be provided for update")
        raise ValueError("At least one field (other than hub_id) must be provided for update")
 
    # Normalize status value (Active/Deactive)
    if "status" in update_fields:
        update_fields["status"] = update_fields["status"].title()
 
    # Ensure new hub_manager not already assigned to another active hub
    if "hub_manager" in update_fields and update_fields["hub_manager"]:
        existing = await db[COLLECTION_HUBS].find_one({
            "hub_manager": update_fields["hub_manager"],
            "status": "Active",
            "hub_id": {"$ne": hub_id_norm}
        })
        if existing:
            logger.error(
                f"Manager '{update_fields['hub_manager']}' already assigned to active hub {existing.get('hub_id')}"
            )
            raise ValueError(
                f"Manager '{update_fields['hub_manager']}' already assigned to active hub {existing.get('hub_id')}"
            )
 
    # Add updated_at timestamp
    update_fields["updated_at"] = _now_utc()

    # Perform update
    result = await db[COLLECTION_HUBS].update_one({"hub_id": hub_id_norm}, {"$set": update_fields})
    if result.matched_count == 0:
        logger.error("LookupError : Hub not found (hub_id=%s)", hub_id_norm)
        raise LookupError("Hub not found")
 
    logger.info("Hub updated successfully: %s", update_fields)
    return {"message": "Hub details updated successfully", "hub_id": hub_id_norm}
 
 
# --------------------------
# Delete (archive) hub
# --------------------------
async def delete_hub(
    hub_id: str,
    hub_name: str,
    hub_manager: Optional[str] = None,
    deleted_by: Optional[str] = None,
    reason: Optional[str] = None
) -> Dict:
    """Archive hub: move from active hubs to closed hubs collection."""
    hub_id_norm = _normalize_hub_id(hub_id)

    # Verify hub exists
    q = {"hub_id": hub_id_norm}
    found = await db[COLLECTION_HUBS].find_one(q)
    if not found:
        logger.error("LookupError : Hub not found (hub_id=%s)", hub_id_norm)
        raise LookupError("Hub not found")
 
    # Validate provided hub_name matches stored record
    if hub_name.strip() != found.get("hub_name"):
        logger.error("hub_name does not match stored record (provided=%s, stored=%s)", hub_name, found.get("hub_name"))
        raise ValueError("hub_name does not match stored record")

    # Validate provided hub_manager matches (if provided)
    if hub_manager and found.get("hub_manager") != hub_manager:
        logger.error("hub_manager does not match stored record (provided=%s, stored=%s)", hub_manager, found.get("hub_manager"))
        raise ValueError("hub_manager does not match stored record")
 
    # Calculate duration hub was active
    hub_closed_date = datetime.now(timezone.utc)
    opening = found.get("hub_opening_date") or found.get("created_at") or hub_closed_date
    if opening.tzinfo is None:  # ensure timezone aware
        opening = opening.replace(tzinfo=timezone.utc)
    delta_days = (hub_closed_date - opening).days
 
    # Copy hub details into closed hub record
    closed_doc = dict(found)  # full copy of original record
    closed_doc.update({
        "hub_closed_date": hub_closed_date,
        "no_of_days_active": delta_days,
        "deleted_by": deleted_by,
        "status" : "Closed",
        "reason": reason
    })
 
    # Insert into ClosedHubs, then remove from active hubs
    await db[COLLECTION_CLOSED_HUBS].insert_one(closed_doc)
    await db[COLLECTION_HUBS].delete_one({"hub_id": hub_id_norm})

    logger.info("Hub deleted successfully: hub_id=%s, reason=%s", hub_id_norm, reason)
 
    return {"message": "Hub deleted successfully", "hub_id": hub_id_norm, "hub_name": found.get("hub_name")}
 
 
# --------------------------
# Search hub
# --------------------------
async def search_hub(hub_id: Optional[str] = None, hub_name: Optional[str] = None, skip: int = 0, limit: int = 50) -> List[Dict]:
    """
    Search hubs by ID or Name.
    If no filter provided, returns paginated list of hubs.
    """
    q = {}
    if hub_id:
        q["hub_id"] = _normalize_hub_id(hub_id)
    if hub_name:
        q["hub_name"] = {"$regex": f".*{hub_name.strip()}.*", "$options": "i"}
 
    cursor = db[COLLECTION_HUBS].find(q).skip(skip).limit(limit)
    results = []
    async for doc in cursor:
        doc.pop("_id", None)  # remove internal Mongo ID
        results.append(doc)
    logger.info("Returning %d hubs (filters: hub_id=%s, hub_name=%s)", len(results), hub_id, hub_name)
    return results
 
 
# --------------------------
# List closed hubs
# --------------------------
async def list_closed_hubs(skip: int = 0, limit: int = 50) -> List[Dict]:
    """Return paginated list of archived/closed hubs."""
    cursor = db[COLLECTION_CLOSED_HUBS].find({}).skip(skip).limit(limit)
    results = []
    async for doc in cursor:
        doc.pop("_id", None)
        results.append(doc)
    logger.info("Returning %d closed hubs", len(results))
    return results
 
 
# --------------------------
# List hubs by status
# --------------------------
async def list_by_status(status: str, skip: int = 0, limit: int = 50) -> List[Dict]:
    """Return paginated list of hubs filtered by status."""
    status = status.title()
    if status not in ("Active", "Deactive"):
        logger.error("Invalid status requested: %s", status)
        raise ValueError("status must be 'Active' or 'Deactive'")
    
    cursor = db[COLLECTION_HUBS].find({"status": status}).skip(skip).limit(limit)
    results = []
    async for doc in cursor:
        doc.pop("_id", None)
        results.append(doc)
    logger.info("Returning %d hubs with status=%s", len(results), status)
    return results
