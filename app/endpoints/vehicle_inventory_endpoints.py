import logging
from fastapi import APIRouter
from app.utiles.decoratores import handle_exceptions
from app.services.vehicle_inventory_service import mark_dispatch_received_service
from app.models.inventory import DispatchReceiveRequest

# Configure logger for this module
logger = logging.getLogger(__name__)

# Create API router for Vehicle Inventory Management
router = APIRouter(tags=["Vehicle Inventory Management"])

@handle_exceptions
@router.put("/mark_dispatch_received", response_model=dict)
async def mark_dispatch_received(request: DispatchReceiveRequest):
    """
    Endpoint to mark a dispatched vehicle inventory as received.
    
    Args:
        request (DispatchReceiveRequest): Request body containing the dispatch_id.
        
    Returns:
        dict: Success or error response from the service layer.
    """
    logger.info(f"Received request to mark dispatch as received. Dispatch ID: {request.dispatch_id}")

    try:
        # Call the service layer to update the dispatch status
        response = await mark_dispatch_received_service(request.dispatch_id)
        logger.info(f"Successfully marked dispatch {request.dispatch_id} as received.")
        return response

    except Exception as e:
        # Log the error before letting handle_exceptions decorator manage the exception
        logger.error(f"Error while marking dispatch {request.dispatch_id} as received: {str(e)}", exc_info=True)
        raise
