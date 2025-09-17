import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apis import auth, channels, chats, chat_agents, webhooks, boards, tasks, websockets
from database import engine

app = FastAPI(
    title="Agent Hub API", 
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
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

app.include_router(auth.router)
app.include_router(channels.router)
app.include_router(chats.router)
app.include_router(chat_agents.router)
app.include_router(webhooks.router)
app.include_router(boards.router)
app.include_router(tasks.router)
app.include_router(websockets.router)


@app.get("/")
async def root():
    """API health check."""
    return {"message": "Agent Hub API is running"}