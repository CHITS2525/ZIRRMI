from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import logging
from MVP import prediction_engine  # Corrected import
from fastapi.responses import HTMLResponse, JSONResponse # Import JSONResponse
import uvicorn  # Import uvicorn

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI()

# Allow all origins (frontend access)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the HTML form
@app.get("/", response_class=HTMLResponse)
async def root():
    """Serves the main HTML form."""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Power Outage Reporter</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap" rel="stylesheet">
        <style>
            body {
                font-family: 'Inter', sans-serif;
            }
            .form-container {
                max-width: 600px;
                margin: auto;
                padding: 2rem;
                background-color: #f7fafc;
                border-radius: 0.75rem;
                box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
            }
            .form-header {
                text-align: center;
                margin-bottom: 1.5rem;
            }
            .form-group {
                margin-bottom: 1rem;
            }
            .form-label {
                display: block;
                margin-bottom: 0.5rem;
                font-weight: 600;
                color: #374151;
            }
            .form-input, .form-textarea {
                width: 100%;
                padding: 0.75rem;
                border-radius: 0.375rem;
                border: 1px solid #d1d5db;
                font-size: 1rem;
                line-height: 1.5rem;
                color: #4b5563;
                background-color: #ffffff;
                transition: border-color 0.15s ease-in-out, shadow-sm 0.15s ease-in-out;
            }
            .form-input:focus, .form-textarea:focus {
                outline: none;
                border-color: #3b82f6;
                box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15);
            }
            .form-textarea {
                min-height: 6rem;
                resize: vertical;
            }
            .form-button {
                width: 100%;
                padding: 0.75rem;
                border-radius: 0.375rem;
                background-color: #3b82f6;
                color: #ffffff;
                font-size: 1rem;
                line-height: 1.5rem;
                font-weight: 600;
                cursor: pointer;
                transition: background-color 0.15s ease-in-out, transform 0.1s ease-in-out;
                border: none;
                display: block;
                margin-left: auto;
                margin-right: auto;
            }
            .form-button:hover {
                background-color: #2563eb;
                transform: translateY(-1px);
                box-shadow: 0 2px 4px -1px rgba(0, 0, 0, 0.06);
            }
            .response-message {
                margin-top: 1.5rem;
                padding: 1rem;
                border-radius: 0.375rem;
                text-align: center;
                font-weight: 600;
                font-size: 1rem;
            }
            .error-message {
                color: #dc2626;
                background-color: #fee2e2;
                border: 1px solid #fecaca;
            }
            .success-message {
                color: #16a34a;
                background-color: #f0fdf4;
                border: 1px solid #bbf7d0;
            }
            .hidden {
                display: none;
            }
            #loading {
                margin-top: 1rem;
                text-align: center;
                font-weight: 600;
                color: #3b82f6;
            }
            #prediction {
                margin-top: 1.5rem;
                padding: 1rem;
                border-radius: 0.375rem;
                background-color: #e0f2fe;
                color: #0369a1;
                text-align: center;
                font-weight: 600;
                font-size: 1.2rem;
                border: 1px solid #b0e0f8;
            }
        </style>
    </head>
    <body class="bg-gray-100 flex items-center justify-center min-h-screen">
        <div class="form-container">
            <h1 class="form-header text-2xl font-semibold text-gray-800">Report Power Outage</h1>
            <form id="outageForm" method="POST" class="space-y-6">
                <div class="form-group">
                    <label for="name" class="form-label">Company Name:</label>
                    <input type="text" id="name" name="name" class="form-input" placeholder="e.g., ZESA Holdings" required>
                    <div id="nameError" class="error-message hidden">Please enter the company name.</div>
                </div>
                <div class="form-group">
                    <label for="phone_number" class="form-label">Phone Number:</label>
                    <input type="tel" id="phone_number" name="phone_number"  pattern="[0-9]{10,15}" class="form-input" placeholder="e.g., 2637XXXXXXXX" required>
                    <div id="phoneError" class="error-message hidden">Please enter a valid phone number.</div>
                </div>
                <div class="form-group">
                    <label for="location" class="form-label">Location:</label>
                    <input type="text" id="location" name="location" class="form-input" placeholder="e.g., Harare" required>
                    <div id="locationError" class="error-message hidden">Please enter the location.</div>
                </div>
                <div class="form-group">
                    <label for="details" class="form-label">Details (Optional):</label>
                    <textarea id="details" name="details" class="form-textarea" placeholder="Enter power outage start and end times if known."></textarea>
                </div>
                <button type="submit" id="submitBtn" class="form-button">Report Outage</button>
                <div id="responseMessage" class="response-message hidden"></div>
                <div id="loading" class="hidden">Submitting outage report...</div>
                <div id="prediction" class="hidden"></div>
            </form>
        </div>
        <script>
            const outageForm = document.getElementById('outageForm');
            const nameInput = document.getElementById('name');
            const phoneInput = document.getElementById('phone_number');
            const locationInput = document.getElementById('location');
            const detailsInput = document.getElementById('details');
            const nameError = document.getElementById('nameError');
            const phoneError = document.getElementById('phoneError');
            const locationError = document.getElementById('locationError');
            const responseMessage = document.getElementById('responseMessage');
            const submitBtn = document.getElementById('submitBtn');
            const loadingIndicator = document.getElementById('loading');
            const predictionDiv = document.getElementById('prediction');

            function validateForm() {
                let isValid = true;
                if (!nameInput.value.trim()) {
                    nameError.classList.remove('hidden');
                    isValid = false;
                } else {
                    nameError.classList.add('hidden');
                }
                if (!phoneInput.value.trim()) {
                    phoneError.classList.remove('hidden');
                    isValid = false;
                } else if (!/^[0-9]{10,15}$/.test(phoneInput.value)) {
                    phoneError.textContent = "Please enter a valid phone number with 10-15 digits.";
                    phoneError.classList.remove('hidden');
                    isValid = false;
                }
                else {
                    phoneError.classList.add('hidden');
                }
                if (!locationInput.value.trim()) {
                    locationError.classList.remove('hidden');
                    isValid = false;
                } else {
                    locationError.classList.add('hidden');
                }
                return isValid;
            }



            outageForm.addEventListener('submit', async (event) => {
                event.preventDefault();
                if (!validateForm()) {
                    return;
                }

                submitBtn.disabled = true;
                loadingIndicator.classList.remove('hidden');
                const formData = new FormData(outageForm);
                const data = {
                    name: formData.get('name'),
                    phone_number: formData.get('phone_number'),
                    location: formData.get('location'),
                    details: formData.get('details')
                };

                responseMessage.textContent = "Submitting outage report...";
                responseMessage.classList.remove('hidden', 'error-message', 'success-message');
                predictionDiv.classList.add('hidden');

                try {
                    const response = await fetch('http://127.0.0.1:8000/report-outage', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify(data)
                    });

                    const responseData = await response.json();
                    if (response.ok) {
                        responseMessage.textContent = "Outage report received!";
                        responseMessage.classList.remove('error-message');
                        responseMessage.classList.add('success-message');
                        outageForm.reset();

                        // This is the key part
                        predictionDiv.textContent =  "Prediction: " + responseData.prediction + ", Message: " + responseData.message;
                        predictionDiv.classList.remove('hidden');

                    } else {
                        responseMessage.textContent = responseData.detail || "Failed to report outage.";
                        responseMessage.classList.remove('success-message');
                        responseMessage.classList.add('error-message');
                    }
                } catch (error) {
                    responseMessage.textContent = "An error occurred while reporting the outage.";
                    responseMessage.classList.remove('success-message');
                    responseMessage.classList.add('error-message');
                    console.error('Error:', error);
                } finally {
                    submitBtn.disabled = false;
                    loadingIndicator.classList.add('hidden');
                }
            });
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.post("/report-outage")
async def report_outage(request: Request):
    """
    Handles the submission of power outage reports and returns a prediction from the model.
    """
    data = await request.json()
    logger.info(f"Received outage report: {data}")

    try:
        result = prediction_engine(data)
        prediction = result.get("prediction", "⚠️ No prediction received.")
        return JSONResponse(content={
            "message": result.get("message", "Outage report received."),
            "prediction": prediction
        })

    except Exception as e:
        logger.error(f"Prediction error: {e}")
        raise HTTPException(status_code=500, detail="Prediction failed.")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=10000)
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Mount the static directory to serve index.html and other files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def serve_home():
    return FileResponse("static/index.html")
