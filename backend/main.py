from backend.api import app, get_agent_service

__all__ = ["app", "get_agent_service"]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.api:app", host="0.0.0.0", port=8000, reload=True)
