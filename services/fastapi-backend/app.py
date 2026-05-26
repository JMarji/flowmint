import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import database
import auth_routes
from routers import plaid, accounts, transactions, budgets, bills, properties, property_txns, documents, networth, planning

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Flowmint API", version="1.0.0")

origins = [o.strip() for o in os.environ.get("FRONTEND_ORIGINS", "http://localhost:5173").split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    database.init_pool()
    database.run_migrations()
    logger.info("Flowmint API started")


@app.get("/health")
def health():
    return {"status": "ok", "service": "flowmint"}


app.include_router(auth_routes.router)
app.include_router(plaid.router, prefix="/api")
app.include_router(accounts.router, prefix="/api")
app.include_router(transactions.router, prefix="/api")
app.include_router(budgets.router, prefix="/api")
app.include_router(bills.router, prefix="/api")
app.include_router(properties.router, prefix="/api")
app.include_router(property_txns.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(networth.router, prefix="/api")
app.include_router(planning.router, prefix="/api")
