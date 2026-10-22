import os
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseModel):
    # Application Config
    APP_NAME: str = "Kisan-Vaani"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    # Gnani.ai / Vachana Credentials & Endpoints
    GNANI_API_KEY: str = os.getenv("GNANI_API_KEY", "")
    GNANI_TTS_API_URL: str = os.getenv("GNANI_TTS_API_URL", "https://api.vachana.ai/api/v1/tts/inference")
    GNANI_STT_API_URL: str = os.getenv("GNANI_STT_API_URL", "https://api.vachana.ai/stt/v3")
    GNANI_STT_WS_URL: str = os.getenv("GNANI_STT_WS_URL", "wss://api.vachana.ai/stt/v3/stream")

    # Government Open Data API (data.gov.in)
    DATA_GOV_API_KEY: str = os.getenv("DATA_GOV_API_KEY", "")
    MANDI_RESOURCE_ID: str = "9ef84268-d588-465a-a308-a864a43d0070"

    # LLM Inference Providers (Gnani Evon Sovereign LLM)
    HF_TOKEN: str = os.getenv("HF_TOKEN", "")
    HUGGINGFACE_API_KEY: str = os.getenv("HUGGINGFACE_API_KEY", "")
    EVON_SPACE_ID: str = os.getenv("EVON_SPACE_ID", "luminenio/gnani-evon-v3.3-chat")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    # Supabase Credentials
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_PUBLISHABLE_KEY: str = os.getenv("SUPABASE_PUBLISHABLE_KEY", "")
    SUPABASE_SECRET_KEY: str = os.getenv("SUPABASE_SECRET_KEY", "")


    # Logistics Defaults
    BASE_FREIGHT_COST: float = 350.0  # Base charge for first 10km
    PER_KM_FREIGHT_RATE: float = 16.0  # Rate per km beyond base
    DIESEL_COST_PER_KM: float = 10.5   # When farmer uses own vehicle (consumption estimate)
    APMC_CESS_RATE: float = 0.010      # Standard 1.0% statutory market fee
    HAMALI_PER_QUINTAL: float = 14.0   # Handling / Loading fee per quintal

settings = Settings()
