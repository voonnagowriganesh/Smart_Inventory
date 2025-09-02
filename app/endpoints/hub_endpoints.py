# app/endpoints/hub_endpoints.py

from fastapi import APIRouter, HTTPException, Query
from app.models.hub import RegisterHub, UpdateHub
from app.services.hub_service import (
    create_hub, update_hub, delete_hub,
    search_hub, list_closed_hubs, list_by_status
)
from app.utiles.decoratores import handle_exceptions
from app.utiles.logger import get_logger
from typing import Optional

# Initialize router
router = APIRouter(prefix="/hubs", tags=["Hub Management"])

# Logger instance for this module
logger = get_logger(__name__)

# ======================================================
# Hub Routes
# Provides endpoints for Hub CRUD, search, and reports
# ======================================================


# ---------------- Register Hub ----------------
@router.post("/register", status_code=201)
@handle_exceptions
async def register_hub(payload: RegisterHub):
    """
    Endpoint: Register a new Hub.
    Calls service layer → create_hub.
    """
    logger.info("API Request → Register Hub: id=%s, name=%s", payload.hub_id, payload.hub_name)
    try:
        res = await create_hub(payload)
        logger.info("API Response → Hub registered successfully: id=%s", payload.hub_id)
        return res
    except ValueError as e:
        logger.warning("API Response → Conflict while registering hub: %s", str(e))
        raise HTTPException(status_code=409, detail=str(e))


# ---------------- Update Hub ----------------
@router.put("/update/{hub_id}")
@handle_exceptions
async def update_hub_endpoint(hub_id: str, payload: UpdateHub):
    """
    Endpoint: Update hub details.
    Calls service layer → update_hub.
    """
    logger.info("API Request → Update Hub: id=%s", hub_id)
    try:
        res = await update_hub(hub_id, payload)
        logger.info("API Response → Hub updated successfully: id=%s", hub_id)
        return res
    except ValueError as e:
        logger.warning("API Response → Invalid update request for hub_id=%s. Reason: %s", hub_id, str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except LookupError as e:
        logger.warning("API Response → Hub not found: hub_id=%s", hub_id)
        raise HTTPException(status_code=404, detail=str(e))


# ---------------- Delete Hub ----------------
@router.delete("/delete/{hub_id}")
@handle_exceptions
async def delete_hub_endpoint(hub_id: str, hub_name: str, hub_manager: Optional[str] = None):
    """
    Endpoint: Delete hub (soft delete).
    Calls service layer → delete_hub.
    """
    logger.info("API Request → Delete Hub: id=%s, name=%s, manager=%s", hub_id, hub_name, hub_manager)
    try:
        res = await delete_hub(hub_id, hub_name, hub_manager)
        logger.info("API Response → Hub deleted successfully: id=%s", hub_id)
        return res
    except LookupError as e:
        logger.warning("API Response → Hub not found: hub_id=%s", hub_id)
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        logger.warning("API Response → Invalid hub deletion request: hub_id=%s. Reason: %s", hub_id, str(e))
        raise HTTPException(status_code=400, detail=str(e))


# ---------------- Search Hubs ----------------
@router.get("/search")
@handle_exceptions
async def search_hub_endpoint(
    hub_id: Optional[str] = Query(None),
    hub_name: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 50
):
    """
    Endpoint: Search hubs by ID or Name.
    Supports pagination.
    Calls service layer → search_hub.
    """
    logger.info("API Request → Search Hub: id=%s, name=%s, skip=%s, limit=%s", hub_id, hub_name, skip, limit)

    results = await search_hub(hub_id, hub_name, skip, limit)
    logger.info("API Response → Search completed. Found %s hubs", len(results))
    return {"hubs": results}


# ---------------- Closed Hubs ----------------
@router.get("/closed")
@handle_exceptions
async def closed_hubs_endpoint(skip: int = 0, limit: int = 50):
    """
    Endpoint: List closed hubs.
    Supports pagination.
    Calls service layer → list_closed_hubs.
    """
    logger.info("API Request → List Closed Hubs: skip=%s, limit=%s", skip, limit)
    res = await list_closed_hubs(skip, limit)
    logger.info("API Response → Found %s closed hubs", len(res))
    return {"closed_hubs": res}


# ---------------- Hubs by Status ----------------
@router.get("/status")
@handle_exceptions
async def hubs_by_status_endpoint(status: str = Query(...), skip: int = 0, limit: int = 50):
    """
    Endpoint: List hubs filtered by status.
    Calls service layer → list_by_status.
    """
    logger.info("API Request → List Hubs by Status: status=%s, skip=%s, limit=%s", status, skip, limit)
    try:
        res = await list_by_status(status, skip, limit)
        logger.info("API Response → Found %s hubs with status=%s", len(res), status)
        return {"hubs": res}
    except ValueError as e:
        logger.warning("API Response → Invalid status filter: %s", str(e))
        raise HTTPException(status_code=400, detail=str(e))
