import uvicorn
from fastapi import FastAPI, UploadFile, File, Depends, Query
from typing import List
from fastapi.middleware.cors import CORSMiddleware
from app.database import get_db
from sqlalchemy.orm import Session
from app.routes.auth import router as auth_router
from app.models import Business, User, Document, QueryLog
from app.rag import ingest_document, retrieve_chunks
from app.llm import generate_answer
from pydantic import Field, BaseModel
from app.auth import (
    get_current_user,
)
import os
import uuid
from math import ceil

class AskRequest(BaseModel):
    question: str

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)

@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/items/{item_id}")
def read_item(item_id: int, q: str | None = None):
    return {"item_id": item_id, "q": q}

@app.post("/upload-multiple")
async def upload_documents(
    current_context: User = Depends(get_current_user),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    print('look here')
    user, business_id = current_context
    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        return {"error": "Business not found"}

    uploaded = []

    for file in files:
        # Save uploaded file locally temporarily
        temp_path = f"/tmp/{uuid.uuid4()}_{file.filename}"
        with open(temp_path, "wb") as f:
            f.write(await file.read())

        # Create DB record
        doc = Document(
            business_id=business.id,
            filename=file.filename,
            content="",  # optional; can store raw text or leave blank
            status="ready",
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        chunks_count = ingest_document(
            db          = db,
            business_id = business.id,      # int not string
            document_id = doc.id,           # int not string
            file_path   = temp_path,
            mime_type   = file.content_type,
            filename    = file.filename,
        )

        uploaded.append({
            "filename": file.filename,
            "document_id": doc.id,
            "chunks": chunks_count
        })

        # Remove temp file
        os.remove(temp_path)

    return {"uploaded": uploaded}

from math import ceil
from fastapi import Query

@app.get("/documents")
def get_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_context = Depends(get_current_user),
):
    user, business_id = current_context

    if not business_id:
        return {"error": "No business associated with user"}

    # ✅ FILTER by business_id
    query = db.query(Document).filter(Document.business_id == business_id)

    total_docs = query.count()
    total_pages = ceil(total_docs / page_size) if total_docs > 0 else 1

    documents = (
        query
        .order_by(Document.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    docs_list = [
        {
            "id": str(doc.id),
            "name": doc.filename,
            "type": os.path.splitext(doc.filename)[1].replace(".", "").upper(),
        }
        for doc in documents
    ]

    return {
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "total_documents": total_docs,
        "documents": docs_list,
    }

@app.post("/ask")
def ask_question(
    body: AskRequest,
    db: Session = Depends(get_db),
    current_context = Depends(get_current_user),
):
    user, business_id = current_context

    # 1. Retrieve relevant chunks from pgvector
    chunks = retrieve_chunks(
        db=db,
        business_id=business_id,
        query=body.question,
        top_k=15,
    )

    # 2. If nothing found
    if not chunks:
        return {
            "answer": "I couldn't find that in your documents.",
            "sources": []
        }

    # 3. Generate LLM answer
    answer = generate_answer(body.question, chunks)

    # 4. (Optional but recommended) log query
    db.add(QueryLog(
        business_id=business_id,
        query_text=body.question,
        answer=answer
    ))
    db.commit()

    # 5. Return response + sources
    return {
        "answer": answer,
        "sources": list({c["filename"] for c in chunks}),
        "chunks_used": len(chunks)
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)