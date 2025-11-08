from pydantic import BaseModel, Field
from typing import Optional

class QARequest(BaseModel):
    """Request model for Q&A endpoint (with transcript)"""
    video_id: str = Field(..., description="YouTube video ID")
    transcript: str = Field(..., description="Full video transcript text")
    question: str = Field(..., min_length=1, description="User's question about the video")
    
    class Config:
        json_schema_extra = {
            "example": {
                "video_id": "dQw4w9WgXcQ",
                "transcript": "Never gonna give you up, never gonna let you down...",
                "question": "What is this song about?"
            }
        }

class AutoQARequest(BaseModel):
    """Request model for automatic Q&A endpoint (fetches transcript automatically)"""
    video_id: str = Field(..., description="YouTube video ID")
    question: str = Field(..., min_length=1, description="User's question about the video")
    session_id: Optional[str] = Field(None, description="Optional session ID for conversation memory")
    clear_history: Optional[bool] = Field(False, description="Clear conversation history for this session")
    
    class Config:
        json_schema_extra = {
            "example": {
                "video_id": "UtXzdmpysmU",
                "question": "What is this video about?",
                "session_id": "user-123",
                "clear_history": False
            }
        }

class QAResponse(BaseModel):
    """Response model for Q&A endpoint"""
    success: bool
    answer: Optional[str] = None
    error: Optional[str] = None
    video_id: Optional[str] = None
    transcript_fetched: Optional[bool] = None  # True if transcript was auto-fetched
    session_id: Optional[str] = None  # Session ID for conversation tracking
    conversation_length: Optional[int] = None  # Number of exchanges in conversation
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "answer": "The song is about commitment and loyalty in a relationship...",
                "error": None,
                "video_id": "dQw4w9WgXcQ",
                "transcript_fetched": False,
                "session_id": "user-123",
                "conversation_length": 3
            }
        }

class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    message: str
    azure_configured: bool
    missing_settings: Optional[list[str]] = None