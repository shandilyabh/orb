"""
API router for generic data CRUD operations.
"""
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status, Request # type: ignore
from pymongo import MongoClient # type: ignore
from pymongo.errors import PyMongoError # type: ignore

from redis import Redis # type: ignore
from api.dependencies import (get_current_user,
                              get_userdb_client, # type: ignore
                              get_data_client,  # type: ignore
                              get_redis_client) # type: ignore
from api.custom_responses import ORJSONResponse
from models.pydantic_models import CountResponse, DataQuery, DataUpdate, StatusResponse, TokenData
from services.exceptions import (AuthorizationError, DatabaseError,
                                 DocumentNotFoundError)
from services.query_router import QueryRouter

router = APIRouter(prefix="/data", tags=["Data Operations"])


@router.post("/find_one")
async def find_one_document(
    request: Request,
    request_data: DataQuery,
    current_user: TokenData = Depends(get_current_user),
    userdb_client: MongoClient = Depends(get_userdb_client),
    data_client: MongoClient = Depends(get_data_client),
    redis_client: Redis = Depends(get_redis_client),
):
    """
    Fetches a single document from a specified collection.
    """
    payload = {
        "op": "find_one",
        "info": current_user.model_dump(),
        "db": request_data.db,
        "coll": request_data.collection,
        "request": {"query": request_data.query, "projection": request_data.projection},
    }
    try:
        query_router = QueryRouter(userdb_client=userdb_client, data_client=data_client, redis_client=redis_client)
        document = query_router.route_query(request, payload)

        if '_id' in document.keys():
            document['_id'] = str(document['_id'])
            
        return ORJSONResponse(content={"status_code": 200, "data": document})
    except DocumentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except AuthorizationError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except (DatabaseError, ValueError, PyMongoError) as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/find")
async def find_documents(
    request: Request,
    request_data: DataQuery,
    current_user: TokenData = Depends(get_current_user),
    userdb_client: MongoClient = Depends(get_userdb_client),
    data_client: MongoClient = Depends(get_data_client),
    redis_client: Redis = Depends(get_redis_client),
):
    """
    Fetches a list of documents from a specified collection based on a query.
    """
    payload = {
        "op": "find",
        "info": current_user.model_dump(),
        "db": request_data.db,
        "coll": request_data.collection,
        "request": {
            "query": request_data.query,
            "projection": request_data.projection,
            "sort": request_data.sort,
            "limit": request_data.limit,
            "offset": request_data.offset,
            "batch_size": request_data.batch_size,
        },
    }
    try:
        query_router = QueryRouter(userdb_client=userdb_client, data_client=data_client, redis_client=redis_client)
        documents = query_router.route_query(request, payload)
        
        for doc in documents:
            if "_id" in doc.keys():
                doc["_id"] = str(doc["_id"])
        
        return ORJSONResponse(content={"status_code": 200, "data": documents})
    except AuthorizationError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except (DatabaseError, ValueError, PyMongoError) as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/count_documents", response_model=CountResponse)
async def count_documents(
    request: Request,
    request_data: DataQuery,
    current_user: TokenData = Depends(get_current_user),
    userdb_client: MongoClient = Depends(get_userdb_client),
    data_client: MongoClient = Depends(get_data_client),
    redis_client: Redis = Depends(get_redis_client),
):
    """
    Counts the number of documents matching the query.
    """
    payload = {
        "op": "count_documents",
        "info": current_user.model_dump(),
        "db": request_data.db,
        "coll": request_data.collection,
        "request": {"query": request_data.query},
    }
    try:
        query_router = QueryRouter(userdb_client=userdb_client, data_client=data_client, redis_client=redis_client)
        document_count = query_router.route_query(request, payload)
        return CountResponse(count=document_count)
    except AuthorizationError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except (DatabaseError, ValueError, PyMongoError) as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/insert_one", response_model=StatusResponse)
async def insert_one_document(
    request: Request,
    request_data: DataQuery,
    current_user: TokenData = Depends(get_current_user),
    userdb_client: MongoClient = Depends(get_userdb_client),
    data_client: MongoClient = Depends(get_data_client),
    redis_client: Redis = Depends(get_redis_client),
):
    """
    Inserts a single document into a specified collection.

    Note: The 'query' field of the request body should contain the document to insert.
    """
    payload = {
        "op": "insert_one",
        "info": current_user.model_dump(),
        "db": request_data.db,
        "coll": request_data.collection,
        "request": {"document": request_data.query},
    }
    try:
        query_router = QueryRouter(userdb_client=userdb_client, data_client=data_client, redis_client=redis_client)
        query_router.route_query(request, payload)
        return StatusResponse(message="Document inserted successfully.")
    except AuthorizationError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except (DatabaseError, ValueError, PyMongoError) as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/update_one", response_model=StatusResponse)
async def update_one_document(
    request: Request,
    request_data: DataUpdate,
    current_user: TokenData = Depends(get_current_user),
    userdb_client: MongoClient = Depends(get_userdb_client),
    data_client: MongoClient = Depends(get_data_client),
    redis_client: Redis = Depends(get_redis_client),
):
    """
    Updates a single document in a specified collection.
    """
    payload = {
        "op": "update_one",
        "info": current_user.model_dump(),
        "db": request_data.db,
        "coll": request_data.collection,
        "request": {"query": request_data.query, "op": request_data.update},
    }
    try:
        query_router = QueryRouter(userdb_client=userdb_client, data_client=data_client, redis_client=redis_client)
        query_router.route_query(request, payload)
        return StatusResponse(message="Document updated successfully.")
    except DocumentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except AuthorizationError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except (DatabaseError, ValueError, PyMongoError) as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/delete_one", response_model=StatusResponse)
async def delete_one_document(
    request: Request,
    request_data: DataQuery,
    current_user: TokenData = Depends(get_current_user),
    userdb_client: MongoClient = Depends(get_userdb_client),
    data_client: MongoClient = Depends(get_data_client),
    redis_client: Redis = Depends(get_redis_client),
):
    """
    Deletes a single document from a specified collection.
    """
    payload = {
        "op": "delete_one",
        "info": current_user.model_dump(),
        "db": request_data.db,
        "coll": request_data.collection,
        "request": {"query": request_data.query},
    }
    try:
        query_router = QueryRouter(userdb_client=userdb_client, data_client=data_client, redis_client=redis_client)
        query_router.route_query(request, payload)
        return StatusResponse(message="Document deleted successfully.")
    except DocumentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except AuthorizationError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except (DatabaseError, ValueError, PyMongoError) as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
