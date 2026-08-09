import io
import os
import soundfile as sf
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from kokoro_onnx import Kokoro

app = FastAPI(title="GCP Custom TTS Service (Kokoro ONNX)")

# Lazy load Kokoro ONNX model at startup
kokoro = None

@app.on_event("startup")
def startup_event():
    global kokoro
    try:
        if os.path.exists("kokoro-v0_19.onnx") and os.path.exists("voices.bin"):
            kokoro = Kokoro("kokoro-v0_19.onnx", "voices.bin")
            print("Kokoro model and voices loaded successfully!")
        else:
            print("WARNING: Model files not found. They should be downloaded via download_model.py during docker build.")
    except Exception as e:
        print(f"Error loading model: {e}")

class TTSRequest(BaseModel):
    text: str
    voice: str = "af_bella"  # Default high-quality female voice
    speed: float = 1.0
    emotion: str = "neutral"

@app.post("/synthesize")
async def synthesize(request: TTSRequest):
    global kokoro
    if not kokoro:
        # Try to load if not initialized
        import os
        if os.path.exists("kokoro-v0_19.onnx") and os.path.exists("voices.bin"):
            kokoro = Kokoro("kokoro-v0_19.onnx", "voices.bin")
        else:
            raise HTTPException(status_code=500, detail="TTS Model files not found on server.")
            
    try:
        # Map default/empty voice to a valid Kokoro voice
        voice = request.voice
        if voice == "default" or not voice:
            voice = "af_bella"
            
        # Generate raw speech samples and sample rate
        samples, sample_rate = kokoro.create(
            request.text, 
            voice=voice, 
            speed=request.speed
        )
        
        # Write to memory buffer in WAV format
        buffer = io.BytesIO()
        sf.write(buffer, samples, sample_rate, format="WAV")
        buffer.seek(0)
        
        from fastapi.responses import StreamingResponse
        return StreamingResponse(buffer, media_type="audio/wav")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    return {"status": "healthy", "model_loaded": kokoro is not None}
