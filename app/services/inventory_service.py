# app/services/inventory_service.py
"""
Async service layer for Inventory Management (Motor + FastAPI).
Paste into app/services/inventory_service.py
"""
from typing import Dict, List, Optional, Any
from uuid import uuid4

from pymongo.errors import DuplicateKeyError


from app.models.inventory import RegisterInventory,UpdateInventory,DispatchRequest,BatchOut,ProductSummaryOut,DispatchOut,StockTransactionOut
from app.db.mongodb import db
from app.utiles.logger import get_logger
from app.core.config import COLLECTION_HUBS  # ensure this exists in your config
from app.utiles.custom_helpers import _now_utc,_to_utc_datetime_from_date, _normalize_id, _gen_transaction_id, _gen_dispatch_id

logger = get_logger(__name__)

# Collection names (string constants)
COL_INV_PRODUCTS = "InventoryProducts"
COL_INV_BATCHES = "InventoryBatches"
COL_STOCK_TX = "StockTransactions"
COL_DISPATCHES = "Dispatches"



# ----------------------------
# Internal helpers (DB checks)
# ----------------------------
async def _ensure_db():
    # Ensure DB is initialized
    if db is None:
        logger.error("Database is not initialized")
        raise RuntimeError("Database connection not established")

async def _ensure_hub_exists(hub_id: str) -> Dict[str, Any]:
    # Ensure hub exists in master hubs collection
    await _ensure_db()
    hub = await db[COLLECTION_HUBS].find_one({"hub_id": _normalize_id(hub_id)})
    if not hub:
        logger.error(f"Hub_ID '{hub_id}' not found")
        raise ValueError(f"Hub_ID '{hub_id}' not found")
    return hub

async def _get_product_master(product_id: str) -> Optional[Dict[str, Any]]:
    # Fetch product master record by Product_ID
    await _ensure_db()
    return await db[COL_INV_PRODUCTS].find_one({"Product_ID": _normalize_id(product_id)})

async def _get_total_available(product_id: str, hub_id: str) -> int:
    # Compute total available stock for a product in a hub
    await _ensure_db()
    pipeline = [
        {"$match": {"Product_ID": _normalize_id(product_id), "Hub_ID": _normalize_id(hub_id), "status": "active"}},
        {"$group": {"_id": None, "total": {"$sum": "$Quantity"}}}
    ]
    res = await db[COL_INV_BATCHES].aggregate(pipeline).to_list(length=1)
    if not res:
        return 0
    return int(res[0].get("total", 0))

# ----------------------------
# Main service functions
# ----------------------------

async def register_inventory(payload : RegisterInventory) -> Dict[str, Any]:
    """
    Register inventory: create product master (if needed) and create/merge a batch.
    payload: instance of RegisterInventory Pydantic (or dict with same keys)
    """
    await _ensure_db()

    hub_id = _normalize_id(payload.Hub_ID)
    product_id = _normalize_id(payload.Product_ID)
    product_name = payload.Product_Name.strip()

    # 1) Validate Hub exists
    await _ensure_hub_exists(hub_id)

    now = _now_utc()
    expiry_dt = _to_utc_datetime_from_date(payload.Expiry_Date)

    # 2) Ensure product master (create if not exist)
    product_master = await db[COL_INV_PRODUCTS].find_one({"Product_ID": product_id})
    if not product_master:
        master_doc = {
            "Product_ID": product_id,
            "Product_Name": product_name,
            "Category": payload.Category.strip(),
            "Brand": payload.Brand.strip() if payload.Brand else None,
            "Selling_Price": payload.Selling_Price,
            "Product_Description": payload.Product_Description,
            "created_at": now,
            "updated_at": now,
        }
        try:
            await db[COL_INV_PRODUCTS].insert_one(master_doc)
            logger.info("Inserted product master %s", product_id)
        except DuplicateKeyError:
            # race: another process created it; re-fetch
            product_master = await db[COL_INV_PRODUCTS].find_one({"Product_ID": product_id})
    else:
        # optional: update master meta if provided (e.g., Selling_Price changed)
        update_master = {}
        if payload.Selling_Price is not None and product_master.get("Selling_Price") != payload.Selling_Price:
            update_master["Selling_Price"] = payload.Selling_Price
        if payload.Product_Description and payload.Product_Description != product_master.get("Product_Description"):
            update_master["Product_Description"] = payload.Product_Description
        if update_master:
            update_master["updated_at"] = now
            await db[COL_INV_PRODUCTS].update_one({"Product_ID": product_id}, {"$set": update_master})
            logger.info("Updated product master details for %s", product_id)

    # 3) Determine Batch_No and check existing batch (by Batch_No or by Product+Hub+Expiry)
    batch_no = payload.Batch_No.strip() if payload.Batch_No else None

    if batch_no:
        existing_batch = await db[COL_INV_BATCHES].find_one({"Product_ID": product_id, "Hub_ID": hub_id, "Batch_No": batch_no})
    else:
        # try to find batch by exact expiry match
        existing_batch = await db[COL_INV_BATCHES].find_one({
            "Product_ID": product_id,
            "Hub_ID": hub_id,
            "Expiry_Date": expiry_dt,
            "status": "active"
        })

    unit_price = (payload.Value / payload.Quantity) if payload.Quantity > 0 else 0.0

    if existing_batch:
        # Merge into existing batch (weighted average for purchase unit price)
        old_qty = existing_batch.get("Quantity", 0)
        old_val = existing_batch.get("Purchase_Value", 0.0)
        new_qty = old_qty + payload.Quantity
        new_total_value = old_val + float(payload.Value)
        new_unit_price = ( (existing_batch.get("Purchase_Unit_Price", 0.0) * old_qty) + (unit_price * payload.Quantity) ) / new_qty if new_qty>0 else unit_price

        update_doc = {
            "$inc": {"Quantity": payload.Quantity, "Purchase_Value": float(payload.Value)},
            "$set": {"Purchase_Unit_Price": float(new_unit_price), "last_updated": now}
        }
        await db[COL_INV_BATCHES].update_one({"_id": existing_batch["_id"]}, update_doc)
        batch_no_used = existing_batch["Batch_No"]
        logger.info("Merged into existing batch %s (product=%s, hub=%s)", batch_no_used, product_id, hub_id)
    else:
        # Create new batch
        if not batch_no:
            batch_no = f"{product_id}-{hub_id}-{_now_utc().strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}"
        batch_doc = {
            "Product_ID": product_id,
            "Hub_ID": hub_id,
            "Batch_No": batch_no,
            "Quantity": int(payload.Quantity),
            "Expiry_Date": expiry_dt,
            "Purchase_Value": float(payload.Value),
            "Purchase_Unit_Price": float(unit_price),
            "status": "active",
            "created_at": now,
            "last_updated": now
        }
        try:
            await db[COL_INV_BATCHES].insert_one(batch_doc)
            logger.info("Created new batch %s for product %s", batch_no, product_id)
        except DuplicateKeyError:
            logger.warning("DuplicateKeyError on batch insert; merging fallback")
            # race: another process created the same batch; merge fallback
            existing_batch = await db[COL_INV_BATCHES].find_one({"Product_ID": product_id, "Hub_ID": hub_id, "Batch_No": batch_no})
            if existing_batch:
                await db[COL_INV_BATCHES].update_one({"_id": existing_batch["_id"]}, {"$inc": {"Quantity": payload.Quantity, "Purchase_Value": float(payload.Value)}, "$set": {"last_updated": now}})
            else:
                logger.exception("Failed to handle duplicate batch creation")
                raise

        batch_no_used = batch_no

    # 4) Insert stock transaction (IN)
    txn = {
        "transaction_id": _gen_transaction_id(),
        "type": "IN",
        "Product_ID": product_id,
        "Hub_ID": hub_id,
        "Batch_No": batch_no_used,
        "Quantity": int(payload.Quantity),
        "Unit_Price": float(unit_price),
        "Total_Value": float(payload.Value),
        "reference": payload.Purchase_Ref if hasattr(payload, "Purchase_Ref") else None,
        "timestamp": now,
        "remarks": "Register Inventory"
    }
    await db[COL_STOCK_TX].insert_one(txn)
    logger.info("Inserted stock transaction %s", txn["transaction_id"])

    # 5) Determine warning if expiry within 30 days
    days_left = (expiry_dt - now).days
    warning = None
    if days_left < 30:
        warning = f"{payload.Product_Name} will expire within {days_left} days"

    # 6) Return response
    return {
        "message": "Product batch added successfully",
        "Hub_ID": hub_id,
        "Hub_Name": (await db[COLLECTION_HUBS].find_one({"hub_id": hub_id})).get("hub_name"),
        "Product_ID": product_id,
        "Batch_No": batch_no_used,
        "Quantity_Added": int(payload.Quantity),
        "warning": warning
    }


async def update_inventory(payload: UpdateInventory) -> Dict[str, Any]:
    """
    Update existing product by adding stock or updating master fields.
    payload: UpdateInventory instance
    """
    await _ensure_db()

    hub_id = _normalize_id(payload.Hub_ID)
    product_id = _normalize_id(payload.Product_ID)
    now = _now_utc()

    # Validate hub & product
    await _ensure_hub_exists(hub_id)
    product_master = await _get_product_master(product_id)
    if not product_master:
        logger.error("Product_ID '%s' not found in master", product_id)
        raise ValueError(f"Product_ID '{product_id}' not found in master. Register product first.")
    
    logger.info("Updating inventory for product %s in hub %s", product_id, hub_id)

    # Update master fields if provided
    master_update = {}
    if payload.Product_Name:
        master_update["Product_Name"] = payload.Product_Name.strip()
    if payload.Selling_Price is not None:
        master_update["Selling_Price"] = payload.Selling_Price
    if payload.Category is not None:
        master_update["Category"] = payload.Category.strip()
    if payload.Product_Description is not None:
        master_update["Product_Description"] = payload.Product_Description
    if payload.Brand is not None:
        master_update["Brand"] = payload.Brand
    if master_update:
        master_update["updated_at"] = now
        await db[COL_INV_PRODUCTS].update_one({"Product_ID": product_id}, {"$set": master_update})
        logger.info("Updated product master fields for %s", product_id)

    # If no quantity to add, return success for master update
    if not payload.Quantity:
        logger.info("No quantity provided. Master fields updated only.")
        return {"Product_ID": product_id, "message": "Product master updated successfully"}

    # We are adding stock: determine batch merge/create
    # Find existing batch by Batch_No or Expiry_Date
    expiry_dt = _to_utc_datetime_from_date(payload.Expiry_Date) if payload.Expiry_Date else None
    batch_no = payload.Batch_No.strip() if payload.Batch_No else None
    unit_price = (payload.Value / payload.Quantity) if payload.Quantity and payload.Value is not None else None

    existing_batch = None
    if batch_no:
        existing_batch = await db[COL_INV_BATCHES].find_one({"Product_ID": product_id, "Hub_ID": hub_id, "Batch_No": batch_no})
    elif expiry_dt:
        existing_batch = await db[COL_INV_BATCHES].find_one({"Product_ID": product_id, "Hub_ID": hub_id, "Expiry_Date": expiry_dt, "status": "active"})

    if existing_batch:
        # Merge into existing batch
        old_qty = existing_batch.get("Quantity", 0)
        old_val = existing_batch.get("Purchase_Value", 0.0)
        new_qty = old_qty + payload.Quantity
        new_unit_price = ((existing_batch.get("Purchase_Unit_Price", 0.0) * old_qty) + ((unit_price or existing_batch.get("Purchase_Unit_Price", 0.0)) * payload.Quantity)) / new_qty if new_qty>0 else (unit_price or existing_batch.get("Purchase_Unit_Price", 0.0))

        update_doc = {
            "$inc": {"Quantity": payload.Quantity, "Purchase_Value": float(payload.Value or 0.0)},
            "$set": {"Purchase_Unit_Price": float(new_unit_price), "last_updated": now}
        }
        await db[COL_INV_BATCHES].update_one({"_id": existing_batch["_id"]}, update_doc)
        batch_no_used = existing_batch["Batch_No"]
        merged = True
        logger.info("Merged stock into existing batch %s", batch_no_used)
    else:
        # Create new batch
        if not batch_no:
            batch_no = f"{product_id}-{hub_id}-{_now_utc().strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}"
        batch_doc = {
            "Product_ID": product_id,
            "Hub_ID": hub_id,
            "Batch_No": batch_no,
            "Quantity": int(payload.Quantity),
            "Expiry_Date": expiry_dt,
            "Purchase_Value": float(payload.Value or 0.0),
            "Purchase_Unit_Price": float(unit_price or 0.0),
            "status": "active",
            "created_at": now,
            "last_updated": now
        }
        await db[COL_INV_BATCHES].insert_one(batch_doc)
        batch_no_used = batch_no
        merged = False
        logger.info("Created new batch %s for product %s", batch_no_used, product_id)

    # Insert stock transaction
    txn = {
        "transaction_id": _gen_transaction_id(),
        "type": "IN",
        "Product_ID": product_id,
        "Hub_ID": hub_id,
        "Batch_No": batch_no_used,
        "Quantity": int(payload.Quantity),
        "Unit_Price": float(unit_price or 0.0),
        "Total_Value": float(payload.Value or 0.0),
        "reference": None,
        "timestamp": now,
        "remarks": "Update Inventory - Add Stock"
    }
    await db[COL_STOCK_TX].insert_one(txn)
    logger.info("Inserted stock transaction %s", txn["transaction_id"])

    # warning for expiry if relevant
    warning = None
    if expiry_dt:
        days_left = (expiry_dt - now).days
        if days_left < 30:
            warning = f"Stock for {product_id} will expire within {days_left} days"
            logger.warning(warning)

    return {
        "Product_ID": product_id,
        "Batch_No": batch_no_used,
        "message": "Product updated successfully in hub",
        "Merged": merged,
        "NewQuantityTotalInBatch": int((await db[COL_INV_BATCHES].find_one({"Batch_No": batch_no_used}))["Quantity"]),
        "warning": warning
    }


async def dispatch_inventory(payload:DispatchRequest) -> Dict[str, Any]:
    """
    Dispatch product from From_Hub to To_Hub using FIFO consumption by expiry.
    payload: DispatchRequest instance
    """
    await _ensure_db()
    from_hub = _normalize_id(payload.From_Hub_ID)
    to_hub = _normalize_id(payload.To_Hub_ID)
    product_id = _normalize_id(payload.Product_ID)
    qty_to_dispatch = int(payload.Quantity)
    now = _now_utc()

    # Validate hubs
    await _ensure_hub_exists(from_hub)
    await _ensure_hub_exists(to_hub)

    logger.info("Dispatching %s units of %s from hub %s to hub %s", qty_to_dispatch, product_id, from_hub, to_hub)

    # Validate product availability
    total_available = await _get_total_available(product_id, from_hub)
    if qty_to_dispatch > total_available:
        logger.error("Insufficient stock in hub %s. Requested %s, available %s", from_hub, qty_to_dispatch, total_available)
        raise ValueError(f"Requested quantity ({qty_to_dispatch}) greater than available stock ({total_available}) at hub {from_hub}")

    # FIFO consumption: batches sorted by Expiry_Date asc, created_at asc
    cursor = db[COL_INV_BATCHES].find({
        "Product_ID": product_id,
        "Hub_ID": from_hub,
        "status": "active",
        "Quantity": {"$gt": 0}
    }).sort([("Expiry_Date", 1), ("created_at", 1)])

    remaining = qty_to_dispatch
    batch_consumption = []  # list of dicts {Batch_No, Qty, Unit_Cost}
    async for batch in cursor:
        if remaining <= 0:
            break
        available_in_batch = int(batch.get("Quantity", 0))
        if available_in_batch <= 0:
            continue
        take = available_in_batch if available_in_batch <= remaining else remaining

        # Atomic decrement (best-effort)
        await db[COL_INV_BATCHES].update_one({"_id": batch["_id"]}, {"$inc": {"Quantity": -take}, "$set": {"last_updated": now}})
        # If batch becomes zero, mark depleted
        new_qty_doc = await db[COL_INV_BATCHES].find_one({"_id": batch["_id"]})
        if new_qty_doc and new_qty_doc.get("Quantity", 0) <= 0:
            await db[COL_INV_BATCHES].update_one({"_id": batch["_id"]}, {"$set": {"status": "depleted", "last_updated": now}})

        unit_cost = float(batch.get("Purchase_Unit_Price", 0.0))
        batch_consumption.append({"Batch_No": batch["Batch_No"], "Qty": int(take), "Unit_Cost": unit_cost})

        # Stock transaction (OUT)
        txn = {
            "transaction_id": _gen_transaction_id(),
            "type": "OUT",
            "Product_ID": product_id,
            "Hub_ID": from_hub,
            "Batch_No": batch["Batch_No"],
            "Quantity": int(take),
            "Unit_Price": unit_cost,
            "Total_Value": float(unit_cost * take),
            "reference": None,
            "timestamp": now,
            "remarks": f"Dispatch to {to_hub}"
        }
        await db[COL_STOCK_TX].insert_one(txn)
        logger.debug("Recorded stock transaction (OUT): %s", txn)

        remaining -= take

        logger.info(
            "Batch %s dispatched %s units, Remaining to dispatch=%s",
            batch["Batch_No"], take, remaining
        )

    # Create dispatch record in Dispatches collection
    dispatch_id = _gen_dispatch_id()
    disp_doc = {
        "dispatch_id": dispatch_id,
        "Product_ID": product_id,
        "From_Hub_ID": from_hub,
        "To_Hub_ID": to_hub,
        "Quantity": qty_to_dispatch,
        "Batch_Consumption": batch_consumption,
        "Vehicle_Assigned": "In-Progress",
        "Driver_Assigned": "In-Progress",
        "Timestamp": now,
        "Status": "In-Progress",
        "Request_Ref": getattr(payload, "Request_Ref", None),
        "Notes": getattr(payload, "Notes", None)
    }
    await db[COL_DISPATCHES].insert_one(disp_doc)
    logger.info("📦 Dispatch record created with ID=%s", dispatch_id)
    
    # Check remaining stock after dispatch
    remaining_after = await _get_total_available(product_id, from_hub)
    logger.info(
        "✅ Dispatch completed: %s units of %s from %s to %s. Remaining stock at %s = %s",
        qty_to_dispatch, product_id, from_hub, to_hub, from_hub, remaining_after
    )

    return {
        "message": "Product dispatched successfully",
        "dispatch_id": dispatch_id,
        "Product_ID": product_id,
        "From_Hub": from_hub,
        "To_Hub": to_hub,
        "Quantity_Dispatched": qty_to_dispatch,
        "Batch_Consumption": batch_consumption,
        "Remaining_Quantity": remaining_after
    }


# ----------------------------
# Extra query helpers
# ----------------------------

async def get_product_summary(product_id: str, hub_id: str) -> Dict[str, Any]:
    """
    Fetch a summarized view of a product for a given hub.
    Includes total available quantity, nearest expiry date, and batch count.
    
    Args:
        product_id (str): The unique identifier for the product.
        hub_id (str): The unique identifier for the hub.

    Returns:
        Dict[str, Any]: A dictionary containing product summary details.
    """

    # Ensure DB connection is initialized
    await _ensure_db()

    # Normalize IDs (strip spaces, standardize format, etc.)
    product_id = _normalize_id(product_id)
    hub_id = _normalize_id(hub_id)

    logger.info(f"Fetching product summary | product_id={product_id}, hub_id={hub_id}")
    
    # Fetch product details from master products collection
    product = await db[COL_INV_PRODUCTS].find_one({"Product_ID": product_id})
    if not product:
        logger.error(f"Product not found | product_id={product_id}")
        raise ValueError("Product not found")
    
    # Aggregation pipeline for calculating summary from batches
    pipeline = [
        {"$match": {"Product_ID": product_id, "Hub_ID": hub_id, "status": "active"}},
        {"$group": {
            "_id": "$Product_ID",
            "Total_Quantity": {"$sum": "$Quantity"}, # Sum of all available quantities
            "Nearest_Expiry": {"$min": "$Expiry_Date"}, # Closest expiry date across batches
            "Batches_Count": {"$sum": 1} # Number of active batches
        }}
    ]

    logger.debug(f"Running aggregation pipeline on {COL_INV_BATCHES}: {pipeline}")
    res = await db[COL_INV_BATCHES].aggregate(pipeline).to_list(length=1)

    # Extract summary or fallback to defaults if no batches found
    summary = res[0] if res else {"Total_Quantity": 0, "Nearest_Expiry": None, "Batches_Count": 0}

    logger.info(
        f"Product summary generated | product_id={product_id}, hub_id={hub_id}, "
        f"total_qty={summary.get('Total_Quantity', 0)}, batches={summary.get('Batches_Count', 0)}"
    )

    # Build and return response
    return {
        "Product_ID": product_id,
        "Product_Name": product.get("Product_Name"),
        "Hub_ID": hub_id,
        "Total_Quantity": int(summary.get("Total_Quantity", 0)),
        "Category": product.get("Category"),
        "Brand": product.get("Brand"),
        "Nearest_Expiry": summary.get("Nearest_Expiry"),
        "Batches_Count": int(summary.get("Batches_Count", 0))
    }


# -----------------------------
# inventory_service.py
# -----------------------------

async def list_inventory_batches(
    product_id: str,
    hub_id: str,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 50
) -> dict:
    """
    List inventory batches for a product in a hub with optional status filter and pagination.
    """

    # Ensure DB connection is ready
    await _ensure_db()
    # Build query with mandatory filters
    query = {"Product_ID": product_id.strip(), "Hub_ID": hub_id.strip()}
    # Apply optional status filter if provided
    if status:
        query["status"] = status.strip().lower()
    
    logger.info(
        "Fetching inventory batches | product_id=%s hub_id=%s status=%s skip=%d limit=%d",
        product_id, hub_id, status, skip, limit
    )

    # Fetch batches sorted by Expiry_Date ascending, with pagination
    cursor = db[COL_INV_BATCHES].find(query).sort("Expiry_Date", 1).skip(skip).limit(limit)
    batches = []
    async for batch in cursor:
        # Convert ObjectId to string for JSON serialization
        batch["_id"] = str(batch["_id"])  # Convert ObjectId to string
        batches.append(batch)
    logger.debug("Fetched %d batches for product_id=%s hub_id=%s", len(batches), product_id, hub_id)

    return {"count": len(batches), "batches": batches}


async def list_products_in_hub(
    hub_id: str,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 50
) -> dict:
    """
    List all products in a hub with optional search and pagination.
    """
    # Ensure DB connection is ready
    await _ensure_db()
    query = {}

    # If search term is provided, allow partial match on Product_ID or Product_Name
    if search:
        query["$or"] = [
            {"Product_ID": {"$regex": search.strip(), "$options": "i"}},
            {"Product_Name": {"$regex": search.strip(), "$options": "i"}}
        ]
    logger.info(
        "Fetching products in hub | hub_id=%s search=%s skip=%d limit=%d",
        hub_id, search, skip, limit
    )
    
    # Fetch products sorted alphabetically by Product_Name
    cursor = db[COL_INV_PRODUCTS].find(query).sort("Product_Name", 1).skip(skip).limit(limit)
    products = []
    async for prod in cursor:
        # Convert ObjectId to string for JSON serialization
        prod["_id"] = str(prod["_id"])
        products.append(prod)
    logger.debug("Fetched %d products in hub_id=%s", len(products), hub_id)

    return {"count": len(products), "products": products}
