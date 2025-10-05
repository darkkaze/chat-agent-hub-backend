import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apis import auth, channels, chats, chat_agents, inbound, boards, tasks, websockets, menu
from database import engine

app = FastAPI(
    title="Agent Hub API",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# CORS middleware for development
if os.getenv("ENVIRONMENT", "development") == "development":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )

app.include_router(auth.router, prefix="/api")
app.include_router(channels.router, prefix="/api")
app.include_router(chats.router, prefix="/api")
app.include_router(chat_agents.router, prefix="/api")
app.include_router(inbound.router, prefix="/api")
app.include_router(boards.router, prefix="/api")
app.include_router(tasks.router, prefix="/api")
app.include_router(websockets.router, prefix="/api")
app.include_router(menu.router, prefix="/api")


@app.get("/api/health")
async def root():
    """API health check."""
    return {"message": "Agent Hub API is running"}