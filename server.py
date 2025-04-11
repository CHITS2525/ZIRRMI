from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from MVP import prediction_engine

app = FastAPI()

# 1. Serve static files (HTML, JS, CSS) from the 'static' folder
app.mount("/static", StaticFiles(directory="static"), name="static")

# 2. Serve the index.html page at the root URL
@app.get("/", response_class=HTMLResponse)
async def read_index():
    return FileResponse("static/index.html")

# 3. Handle form submission at /report-outage
@app.post("/report-outage")
async def report_outage(request: Request):
    data = await request.json()
    print("Prediction engine received:", data)
    prediction = prediction_engine(data)
    return JSONResponse(content=prediction)
