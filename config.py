import os
from dotenv import load_dotenv
from pathlib import Path

# Get the backend directory path
BACKEND_DIR = Path(__file__).parent
ENV_FILE = BACKEND_DIR.parent / ".env"  # .env in project root

# Load environment variables from .env file
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)
else:
    # Fallback: try loading from backend directory
    load_dotenv(BACKEND_DIR / ".env")

class Settings:
    """Application settings loaded from environment variables"""
    
    # Azure OpenAI Configuration
    AZURE_OPENAI_API_KEY: str = os.getenv("AZURE_OPENAI_API_KEY", "")
    AZURE_OPENAI_ENDPOINT: str = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    AZURE_OPENAI_API_VERSION: str = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15")
    AZURE_OPENAI_DEPLOYMENT_NAME: str = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "")
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME: str = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME", "")
    
    # API Configuration
    API_TITLE: str = "YouTube Q&A API"
    API_VERSION: str = "1.0.0"
    
    YOUTUBE_API_KEY: str = os.getenv("YOUTUBE_API_KEY", "")
    
    @property
    def azure_openai_url(self) -> str:
        """Construct the full Azure OpenAI API URL"""
        if not self.AZURE_OPENAI_ENDPOINT or not self.AZURE_OPENAI_DEPLOYMENT_NAME:
            raise ValueError("Azure OpenAI endpoint and deployment name must be configured")
        
        # Ensure endpoint doesn't end with /
        endpoint = self.AZURE_OPENAI_ENDPOINT.rstrip('/')
        return f"{endpoint}/openai/deployments/{self.AZURE_OPENAI_DEPLOYMENT_NAME}/chat/completions"
    
    def validate(self) -> bool:
        """Validate that all required settings are present"""
        required = [
            self.AZURE_OPENAI_API_KEY,
            self.AZURE_OPENAI_ENDPOINT,
            self.AZURE_OPENAI_DEPLOYMENT_NAME
        ]
        return all(required)
    
    def get_missing_settings(self) -> list[str]:
        """Get list of missing required settings"""
        missing = []
        if not self.AZURE_OPENAI_API_KEY:
            missing.append("AZURE_OPENAI_API_KEY")
        if not self.AZURE_OPENAI_ENDPOINT:
            missing.append("AZURE_OPENAI_ENDPOINT")
        if not self.AZURE_OPENAI_DEPLOYMENT_NAME:
            missing.append("AZURE_OPENAI_DEPLOYMENT_NAME")
        return missing

# Global settings instance
settings = Settings()