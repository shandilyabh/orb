"""
The logging module.
"""
from pymongo import MongoClient # type: ignore
from models.log_models import LogEntry


class LogManager:
    """
    Writes usage logs to the database in a structured format.
    """
    
    def log(self, client: MongoClient, log_data: LogEntry) -> None:
        """
        Inserts a structured log entry into the database.

        Args:
            client: The MongoClient used to connect to the database.
            log_data: A Pydantic model instance (SuccessRequestLog or FailureRequestLog)
                      containing the structured data to be logged.
        """
        try:
            db = client["userdb"]
            coll = db["usage_logs"]
            log_dict = log_data.model_dump(exclude_none=True)
            
            coll.insert_one(log_dict)
        except Exception as e:
            print(f"--- Database logging failed: {e} ---")
