from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime
from app.utiles.logger import get_logger

logger = get_logger(__name__)

class RegisterHub(BaseModel):
    hub_id : str = Field(...,example = "HUB001")
    hub_name : str = Field(...,example = "Vijayawada Hub")
    hub_manager : str = Field(...,example = "Ravi Teja")
    hub_phone_number : str = Field(...,example = "8885363301")
    hub_address : str = Field(...,example =" 22-16-H21, Singh Nagar 4 th line ,Vijayawada - 520014")

    @validator("hub_id","hub_name",pre= True)
    def strip_and_normalize(cls,v):
        if isinstance(v,str):
            return v.strip()
        return v
    
    @validator("hub_phone_number")
    def phone_must_be_digits(cls,v):

        digits = "".join(filter(str.isdigit,str(v)))
        if not (len(digits)== 10 or len(digits) == 8):
            logger.error("Hub phone should be if landline 8 digits or phone number then 10 digits it should be")
            raise ValueError("Hub phone should be if landline 8 digits or phone number then 10 digits it should be")
        return digits
    

class UpdateHub(BaseModel):
    hub_name : Optional[str] = None
    hub_id : Optional[str] = None
    hub_phone_number : Optional[str] = None
    hub_address : Optional[str] = None
    status : Optional[str]  = None # must be Active or Deactive

    @validator("status")
    def check_status(cls,v):
        if v is None:
            return v
        v = v.strip().title()
        if v not in ("Active", "Deactive"):
            logger.error("Hub status must be 'Active' or 'Deactive'")
            raise ValueError("Hub status must be 'Active' or 'Deactive'")
        return v
    
    @validator("hub_phone_number")
    def phone_must_be_digits(cls,v):

        digits = "".join(filter(str.isdigit,str(v)))
        if not (len(digits)== 10 or len(digits) == 8):
            logger.error("Hub phone should be if landline 8 digits or phone number then 10 digits it should be")
            raise ValueError("Hub phone should be if landline 8 digits or phone number then 10 digits it should be")
        return digits
    

class HubOut(BaseModel):
    hub_id : str
    hub_name : str
    hub_manager : Optional[str]
    hub_phone_number : Optional[str]
    hub_address : Optional[str]
    status : str
    hub_opening_date : datetime
    updated_at : Optional[datetime]

class ClosedHub(HubOut):
    hub_closed_date : datetime
    no_of_days_active : int
    deleted_by : Optional[str]
    reason : Optional[str]