# app/endpoints/inventory_endpoints.py

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from app.models.inventory import RegisterInventory, UpdateInventory, DispatchRequest
from app.services.inventory_service import (
    register_inventory, update_inventory, dispatch_inventory,
    list_inventory_batches, list_products_in_hub, get_product_summary
)
from app.utiles.decoratores import handle_exceptions
from app.utiles.logger import get_logger

# Initialize router
router = APIRouter(prefix="/inventory", tags=["Inventory Management"])

# Logger instance for this module
logger = get_logger(__name__)

# ======================================================
# Inventory Routes
# Provides endpoints for Inventory CRUD, dispatch,
# product summaries, and batch listings.
# ======================================================


# ---------------- Register Inventory ----------------
@router.post("/register", status_code=201)
@handle_exceptions
async def register_inventory_endpoint(payload: RegisterInventory):
    """
    Endpoint: Register new inventory batch in a hub.
    Calls service layer → register_inventory.
    """
    logger.info("API Request → Register Inventory: product_id=%s, hub_id=%s, qty=%s",
                payload.Product_ID, payload.Hub_ID, payload.Quantity)
    try:
        res = await register_inventory(payload)
        logger.info("API Response → Inventory registered successfully: product_id=%s, hub_id=%s",
                    payload.Product_ID, payload.Hub_ID)
        return res
    except ValueError as e:
        logger.warning("API Response → Failed to register inventory: %s", str(e))
        raise HTTPException(status_code=400, detail=str(e))


# ---------------- Update Inventory ----------------
@router.put("/update")
@handle_exceptions
async def update_inventory_endpoint(payload: UpdateInventory):
    """
    Endpoint: Update existing inventory batch.
    Calls service layer → update_inventory.
    """
    logger.info("API Request → Update Inventory: Batch_No=%s, product_id=%s, hub_id=%s",
                payload.Batch_No, payload.Product_ID, payload.Hub_ID)
    try:
        res = await update_inventory(payload)
        logger.info("API Response → Inventory updated successfully: batch_no=%s", payload.Batch_No)
        return res
    except ValueError as e:
        logger.warning("API Response → Failed to update inventory: %s", str(e))
        raise HTTPException(status_code=400, detail=str(e))


# ---------------- Dispatch Inventory ----------------
@router.post("/dispatch")
@handle_exceptions
async def dispatch_inventory_endpoint(payload: DispatchRequest):
    """
    Endpoint: Dispatch stock from one hub to another.
    Calls service layer → dispatch_inventory.
    """
    logger.info("API Request → Dispatch Inventory: product_id=%s, from_hub=%s, to_hub=%s, qty=%s",
                payload.Product_ID, payload.From_Hub_ID, payload.To_Hub_ID, payload.Quantity)
    try:
        res = await dispatch_inventory(payload)
        logger.info("API Response → Inventory dispatched successfully: product_id=%s", payload.Product_ID)
        return res
    except ValueError as e:
        logger.warning("API Response → Dispatch failed: %s", str(e))
        raise HTTPException(status_code=400, detail=str(e))


# ---------------- Product Summary ----------------
@router.get("/summary")
@handle_exceptions
async def product_summary_endpoint(
    product_id: str = Query(..., description="Product ID"),
    hub_id: str = Query(..., description="Hub ID")
):
    """
    Endpoint: Get product summary for a given hub.
    Calls service layer → get_product_summary.
    """
    logger.info("API Request → Product Summary: product_id=%s, hub_id=%s", product_id, hub_id)
    try:
        res = await get_product_summary(product_id, hub_id)
        logger.info("API Response → Product summary retrieved successfully for product_id=%s", product_id)
        return res
    except ValueError as e:
        logger.warning("API Response → Product summary not found: %s", str(e))
        raise HTTPException(status_code=404, detail=str(e))


# ---------------- List Inventory Batches ----------------
@router.get("/batches")
@handle_exceptions
async def list_inventory_batches_endpoint(
    product_id: str,
    hub_id: str,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 50
):
    """
    Endpoint: List all inventory batches for a product in a hub.
    Supports pagination.
    Calls service layer → list_inventory_batches.
    """
    logger.info("API Request → List Inventory Batches: product_id=%s, hub_id=%s, status=%s, skip=%s, limit=%s",
                product_id, hub_id, status, skip, limit)
    res = await list_inventory_batches(product_id, hub_id, status, skip, limit)
    logger.info("API Response → Found %s batches for product_id=%s", len(res), product_id)
    return res


# ---------------- List Products in Hub ----------------
@router.get("/products")
@handle_exceptions
async def list_products_in_hub_endpoint(
    hub_id: str,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 50
):
    """
    Endpoint: List all products available in a hub.
    Supports search + pagination.
    Calls service layer → list_products_in_hub.
    """
    logger.info("API Request → List Products in Hub: hub_id=%s, search=%s, skip=%s, limit=%s",
                hub_id, search, skip, limit)
    res = await list_products_in_hub(hub_id, search, skip, limit)
    logger.info("API Response → Found %s products in hub_id=%s", len(res), hub_id)
    return res
