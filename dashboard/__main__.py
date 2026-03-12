"""Run: python -m dashboard  or  uvicorn dashboard.server:app"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("dashboard.server:app", host="0.0.0.0", port=8042, reload=False)
