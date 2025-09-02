# main.py (project root)
from fastapi import FastAPI
import uvicorn
from app.db.mongodb import connect_to_mongo, close_mongo_connection
from app.endpoints import hub_endpoints,inventory_endpoint,driver_endpoint ,vehicle_endpoint, vehicle_inventory_endpoints
 
app = FastAPI(title="Smart Inventory - Hub Management")
 

app.include_router(hub_endpoints.router, prefix="/api/hub_mangement", tags=["Hub"])
app.include_router(inventory_endpoint.router, prefix="/api/inventory_mangement")
app.include_router(driver_endpoint.router, prefix="/api/driver_mangement")
app.include_router(vehicle_endpoint.router, prefix="/api/vehicle_mangement")
app.include_router(vehicle_inventory_endpoints.router, prefix="/api/vehicle_inventory")




@app.on_event("startup")
async def startup():
    await connect_to_mongo()


 
@app.on_event("shutdown")
async def shutdown():
    await close_mongo_connection()
 
@app.get("/")
async def root():
    return {"message": "Smart Inventory API running"}