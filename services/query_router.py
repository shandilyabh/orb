"""
Query Routing Module
"""
from fastapi import Request # type: ignore
from pymongo import MongoClient # type: ignore
from redis import Redis # type: ignore
from typing import Dict, Any, List, Callable

from .exceptions import AuthorizationError, ExplicitDenyError
from .operations import Mongo


class QueryRouter:
    def __init__(self, userdb_client: MongoClient, data_client: MongoClient, redis_client: Redis):
        self.user_ops = Mongo(mongo_client=userdb_client, redis_client=redis_client)
        self.data_ops = Mongo(mongo_client=data_client, redis_client=redis_client)
        
        self._user_op_names: List[str] = [
            "create_user", "update_user", "delete_user"
        ]
        
        self._data_op_map: Dict[str, Callable] = {
            "find_one": self.data_ops.fetch_document,
            "find": self.data_ops.bulk_fetch_documents,
            "count_documents": self.data_ops.count_documents,
            "insert_one": self.data_ops.insert_document,
            "insert_many": self.data_ops.bulk_insert_documents,
            "update_one": self.data_ops.update_document,
            "update_many": self.data_ops.bulk_update_documents,
            "delete_one": self.data_ops.delete_document,
            "delete_many": self.data_ops.bulk_delete_documents,
        }

    def _validate_auth(self, op_name: str, db: str, coll: str, user_info: dict) -> None:
        """
        Checks if the operation is authorized for the user based on their token.
        Raises AuthorizationError on failure.
        """
        op_type_map = {
            "read": ["find_one", "find", "count_documents"],
            "write": ["insert_one", "insert_many", "update_one", "update_many", "delete_one", "delete_many"],
            "user_management": self._user_op_names
        }

        op_type = None
        for type, ops in op_type_map.items():
            if op_name in ops:
                op_type = type
                break
        
        if not op_type:
            raise AuthorizationError(f"Operation '{op_name}' is not valid.")

        permissions = user_info.get("permissions")
        if not permissions:
            raise AuthorizationError("User has no permissions defined.")

        allowed = permissions.get(op_type)
        is_authorized = False
        if op_type == "user_management" and allowed:
            is_authorized = True
        elif op_type in ["read", "write"]:
            if allowed == "none":
                raise ExplicitDenyError(f"Access for '{op_type}' on '{db}.{coll}' is explicitly denied by policy.")
            if allowed == "all":
                is_authorized = True
            elif isinstance(allowed, dict) and coll in allowed.get(db, []):
                is_authorized = True

        if not is_authorized:
            raise AuthorizationError(f"User not authorized for '{op_type}' on '{db}.{coll}'.")


    def route_query(self, request: Request, payload: Dict[str, Any]) -> Any:
        """
        Routes a payload to the appropriate service function after validation,
        using the correct database client based on the operation type.
        """
        op_name = payload.get("op")
        if not op_name:
            raise ValueError("Operation 'op' not specified in payload.")

        # log context with the specific action being performed.
        if hasattr(request.state, "log_context"):
            request.state.log_context["action"] = op_name

        user_info = payload.get("info")
        if not user_info:
            raise ValueError("User info must be provided for authorization.")
            
        request_args = payload.get("request", {})
        # request_args['auth'] = user_info

        # Dispatch to the correct database client
        if op_name in self._user_op_names:
            self._validate_auth(op_name=op_name, db="userdb", coll="users", user_info=user_info)
            
            operation_func = getattr(self.user_ops, op_name)
            return operation_func(**request_args)

        elif op_name in self._data_op_map:
            db = payload.get("db")
            coll = payload.get("coll")
            if not db or not coll:
                raise ValueError("Database and collection must be specified for data operations.")

            self._validate_auth(op_name=op_name, db=db, coll=coll, user_info=user_info)
            
            operation_func = self._data_op_map[op_name]
            
            request_args['db'] = db
            request_args['coll'] = coll
            
            if op_name == 'insert_many':
                request_args['documents'] = request_args.pop('query', [])

            return operation_func(**request_args)
        
        else:
            raise ValueError(f"Operation '{op_name}' is not supported.")
