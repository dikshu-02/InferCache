
from contextlib import asynccontextmanager

import torch
from fastapi import FastAPI
from pydantic import BaseModel
from transformers import pipeline


# Load the model once when the service starts.
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Loading sentiment analysis model...")

    app.state.sentiment_pipeline = pipeline(
        task="sentiment-analysis",
        model="distilbert/distilbert-base-uncased-finetuned-sst-2-english",
        device=-1,  # Run on CPU
    )

    print("Model loaded successfully!")
    yield


app = FastAPI(lifespan=lifespan)


class PredictionRequest(BaseModel):
    text: str


@app.post("/predict")
def predict(request: PredictionRequest):
    text = request.text.strip()

    if not text:
        return {"error": "Text must not be empty"}

    result = app.state.sentiment_pipeline(text)[0]

    return {
        "input": text,
        "prediction": result["label"].lower(),
        "confidence": round(result["score"], 4),
    }
