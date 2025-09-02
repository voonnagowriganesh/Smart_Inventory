import inspect
from functools import wraps
from fastapi import HTTPException
from app.utiles.logger import get_logger

logger = get_logger(__name__)

def handle_exceptions(func):
    if inspect.iscoroutinefunction(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                logger.info(f"Calling function: {func.__name__}")
                result = await func(*args, **kwargs)
                logger.info(f"Function {func.__name__} completed successfully")
                return result
            except HTTPException as he:
                logger.warning(f"HTTPException in {func.__name__}: {he.detail}")
                raise he
            except Exception as e:
                logger.exception(f"Exception in function: {func.__name__} - {str(e)}")
                raise HTTPException(status_code=500, detail="Internal Server Error")
        return wrapper
    else:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                logger.info(f"Calling function: {func.__name__}")
                result = func(*args, **kwargs)
                logger.info(f"Function {func.__name__} completed successfully")
                return result
            except HTTPException as he:
                logger.warning(f"HTTPException in {func.__name__}: {he.detail}")
                raise he
            except Exception as e:
                logger.exception(f"Exception in function: {func.__name__} - {str(e)}")
                raise HTTPException(status_code=500, detail="Internal Server Error")
        return wrapper
