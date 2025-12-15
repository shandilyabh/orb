"""
Operations Interface for Mongo
"""

import secrets
from typing import Any, Dict, List, Optional

import bcrypt # type: ignore
from bson import ObjectId # type: ignore
from pymongo import MongoClient, cursor # type: ignore
from pymongo.errors import DuplicateKeyError, PyMongoError # type: ignore
from redis import Redis # type: ignore

from .exceptions import (DatabaseError, DocumentNotFoundError,
                         DuplicateUserError, PolicyNotFoundError)


class Mongo:
    def __init__(self, mongo_client: MongoClient, redis_client: Redis):
        self.mongo_client = mongo_client
        self.redis_client = redis_client

    def create_user(
        self,
        user_id: str,
        policy: str,
        metadata: dict,
        perm: dict,
    ) -> str:
        """
        Function to add a user into the users collection and update the Redis cache.
        """
        db = self.mongo_client["userdb"]
        users = db["users"]

        policy_present = db.policy_store.find_one({"policy": policy})
        if not policy_present:
            raise PolicyNotFoundError(f"Policy '{policy}' not found.")

        api_key = secrets.token_urlsafe(32)
        api_key_hash = bcrypt.hashpw(api_key.encode(), salt=bcrypt.gensalt())
        
        doc: Dict[str, Any] = {
            "_id": ObjectId(),
            "user_id": user_id,
            "api_key_hash": api_key_hash,
            "metadata": metadata,
            "role": policy,
        }

        if policy == "admin":
            doc.update({"read": "all", "write": "all", "user_management": True})
        else:
            doc["user_management"] = False
            if perm.get("write") is not None:
                doc["write"] = perm.get("write")
            if perm.get("read") is not None:
                doc["read"] = perm.get("read")

        try:
            # 1. Insert into MongoDB
            users.insert_one(doc)

            # 2. Insert into Redis Cache
            self.redis_client.hset(
                user_id,
                mapping={
                    "api_key_hash": api_key_hash,
                    "role_id": str(doc["_id"]),
                    "role": doc["role"],
                    "name": doc["metadata"].get("name", ""),
                    "dept": doc["metadata"].get("department", ""),
                },
            )

            return api_key
            
        except DuplicateKeyError:
            raise DuplicateUserError(f"User '{user_id}' already exists.")
        except PyMongoError as e:
            raise DatabaseError(f"Failed to create user in DB: {e}")
        except Exception as e:
            # Catch other potential errors, including Redis errors
            raise DatabaseError(f"An unexpected error occurred during user creation: {e}")

    def delete_user(self, user_id: str) -> bool:
        """Deletes a user from MongoDB and the Redis cache."""
        database = self.mongo_client["userdb"]
        collection = database["users"]
        doc = {"user_id": user_id}
        try:
            # 1. Delete from MongoDB
            result = collection.delete_one(doc)
            if result.deleted_count == 0:
                raise DocumentNotFoundError(f"User '{user_id}' not found for deletion.")

            # 2. Delete from Redis Cache
            self.redis_client.delete(user_id)
            return True
        except PyMongoError as e:
            raise DatabaseError(f"Failed to delete user: {e}")
        except Exception as e:
            raise DatabaseError(f"An unexpected error occurred during user deletion: {e}")

    def update_user(self, user_id: str, policy: str = "", permissions: dict = {}) -> bool:
        """Updates a user's policy and/or permissions."""
        database = self.mongo_client["userdb"]
        collection = database["users"]
        
        user_old_info = collection.find_one({"user_id": user_id})
        if not user_old_info:
            raise DocumentNotFoundError(f"User '{user_id}' not found for update.")

        if not permissions and not policy:
            return True # Nothing to update

        updates = {}
        if policy:
            if policy != user_old_info['role']:
                updates["role"] = policy
                if policy == "admin":
                    updates.update({"user_management": True, "read": "all", "write": "all"})
                elif user_old_info['role'] == "admin":
                    updates["user_management"] = False
        
        if permissions.get("read"):
            updates["read"] = permissions["read"]
        if permissions.get("write"):
            updates["write"] = permissions["write"]

        op = {"$set": updates}
        try:
            result = collection.update_one({"user_id": user_id}, op)
            if result.matched_count == 0:
                raise DocumentNotFoundError(f"User '{user_id}' not found for update.")
            return True
        except PyMongoError as e:
            raise DatabaseError(f"Failed to update user: {e}")

    def fetch_document(self, db: str, coll: str, query: dict, projection: Optional[Dict[str, int]] = None) -> Dict:
        """Fetches a single document."""
        database = self.mongo_client[db]
        collection = database[coll]
        try:
            document = collection.find_one(query, projection)
            if document is None:
                raise DocumentNotFoundError(f"Document not found in {db}.{coll} with query {query}")
            
            document["_id"] = str(document["_id"])
            return document
        except PyMongoError as e:
            raise DatabaseError(f"Failed to fetch document: {e}")

    def update_document(self, db: str, coll: str, query: dict, op: dict) -> bool:
        """Updates a single document."""
        database = self.mongo_client[db]
        collection = database[coll]
        try:
            result = collection.update_one(query, op)
            if result.matched_count == 0:
                raise DocumentNotFoundError(f"Document not found in {db}.{coll} for update.")
            return True
        except PyMongoError as e:
            raise DatabaseError(f"Failed to update document: {e}")

    def insert_document(self, db: str, coll: str, query: dict) -> bool:
        """Inserts a single document."""
        database = self.mongo_client[db]
        collection = database[coll]
        try:
            collection.insert_one(query)
            return True
        except PyMongoError as e:
            raise DatabaseError(f"Failed to insert document: {e}")

    def delete_document(self, db: str, coll: str, query: dict) -> bool:
        """Deletes a single document."""
        database = self.mongo_client[db]
        collection = database[coll]
        try:
            result = collection.delete_one(query)
            if result.deleted_count == 0:
                raise DocumentNotFoundError(f"Document not found in {db}.{coll} for deletion.")
            return True
        except PyMongoError as e:
            raise DatabaseError(f"Failed to delete document: {e}")

    def bulk_delete_documents(self, db: str, coll: str, query: dict) -> int:
        """Deletes multiple documents."""
        database = self.mongo_client[db]
        collection = database[coll]
        try:
            result = collection.delete_many(query)
            return result.deleted_count
        except PyMongoError as e:
            raise DatabaseError(f"Failed to bulk delete documents: {e}")

    def bulk_fetch_documents(self, db: str, coll: str, query: dict = {}, projection: Optional[Dict[str, int]] = None, limit: Optional[int] = None, batch_size: Optional[int] = None) -> List[Dict]:
        """Fetches multiple documents."""
        database = self.mongo_client[db]
        collection = database[coll]
        try:
            cursor = collection.find(query, projection)
            if limit:
                cursor = cursor.limit(limit)
            if batch_size:
                cursor = cursor.batch_size(batch_size)
            
            ret = [doc for doc in cursor]
            for doc in ret:
                if "_id" in doc:
                    doc["_id"] = str(doc["_id"])
            return ret
        except PyMongoError as e:
            raise DatabaseError(f"Failed to bulk fetch documents: {e}")

    def bulk_update_documents(self, db: str, coll: str, query: dict, op: dict) -> int:
        """Updates multiple documents."""
        database = self.mongo_client[db]
        collection = database[coll]
        try:
            result = collection.update_many(query, op)
            return result.modified_count
        except PyMongoError as e:
            raise DatabaseError(f"Failed to bulk update documents: {e}")

    def bulk_insert_documents(self, db: str, coll: str, documents: List[dict]) -> int:
        """Inserts multiple documents."""
        database = self.mongo_client[db]
        collection = database[coll]
        try:
            result = collection.insert_many(documents)
            return len(result.inserted_ids)
        except PyMongoError as e:
            raise DatabaseError(f"Failed to bulk insert documents: {e}")
