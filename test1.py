from fastapi import FastAPI
import os

app = FastAPI()

HOST = os.getenv('HOST', 'localhost')
PORT = int(os.getenv('PORT', 8000))

@app.get("/")
async def root():
    return {"message": "Hello World"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
