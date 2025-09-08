from fastapi import FastAPI
from apis import auth, channels, chats, webhooks, boards, tasks
from database import engine

app = FastAPI(
    title="Agent Hub API", 
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.include_router(auth.router)
app.include_router(channels.router)
app.include_router(chats.router)
app.include_router(webhooks.router)
app.include_router(boards.router)
app.include_router(tasks.router)


@app.get("/")
async def root():
    """API health check."""
    return {"message": "Agent Hub API is running"}