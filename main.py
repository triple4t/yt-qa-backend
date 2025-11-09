from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from config import settings
from models.schemas import QARequest, AutoQARequest, QAResponse, HealthResponse
from services.azure_openai import get_azure_service
from services.youtube_transcript import YouTubeTranscriptService
from services.conversation_memory import conversation_memory
from typing import Optional
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION,
    description="Backend API for YouTube Q&A Chrome Extension",
    docs_url="/docs",  # Swagger UI at /docs
    redoc_url="/redoc"  # ReDoc at /redoc
)

# Configure CORS - Allow Chrome extension origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "chrome-extension://*",  # Allow all Chrome extensions
        "http://localhost:*",    # For local testing
        "http://127.0.0.1:*",    # For local testing
        "https://www.youtube.com"  # Allow YouTube origin
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"]
)

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    logger.info("Starting YouTube Q&A API...")
    if settings.validate():
        logger.info("Azure OpenAI configuration validated successfully")
        try:
            # Test service initialization
            get_azure_service()
            logger.info("Azure OpenAI service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Azure OpenAI service: {e}")
    else:
        missing = settings.get_missing_settings()
        logger.warning(f"Azure OpenAI not fully configured. Missing: {', '.join(missing)}")

@app.get("/", response_model=HealthResponse)
async def root():
    """Root endpoint - health check"""
    is_configured = settings.validate()
    missing = settings.get_missing_settings() if not is_configured else None
    
    return HealthResponse(
        status="healthy",
        message="YouTube Q&A API is running",
        azure_configured=is_configured,
        missing_settings=missing
    )

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint with detailed status"""
    is_configured = settings.validate()
    missing = settings.get_missing_settings() if not is_configured else None
    
    return HealthResponse(
        status="healthy",
        message="API is operational" if is_configured else "API is running but Azure OpenAI is not configured",
        azure_configured=is_configured,
        missing_settings=missing
    )

@app.get("/privacy-policy")
async def privacy_policy():
    """Privacy policy page for Chrome Web Store"""
    backend_dir = Path(__file__).parent
    privacy_policy_path = backend_dir / "privacy-policy.html"
    
    if not privacy_policy_path.exists():
        raise HTTPException(status_code=404, detail="Privacy policy not found")
    
    return FileResponse(privacy_policy_path, media_type="text/html")

@app.get("/api/conversation/history")
async def get_conversation_history(video_id: str, session_id: Optional[str] = None):
    """
    Get conversation history for a video session
    
    Query Parameters:
    - video_id: YouTube video ID
    - session_id: Optional session ID (default: uses video_id)
    
    Returns:
    - List of Q&A exchanges in the conversation
    """
    try:
        history = conversation_memory.get_history(video_id, session_id)
        return {
            "video_id": video_id,
            "session_id": session_id or "default",
            "history": history,
            "count": len(history)
        }
    except Exception as e:
        logger.error(f"Error getting conversation history: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving conversation history: {str(e)}"
        )

@app.delete("/api/conversation/history")
async def clear_conversation_history(video_id: str, session_id: Optional[str] = None):
    """
    Clear conversation history for a video session
    
    Query Parameters:
    - video_id: YouTube video ID
    - session_id: Optional session ID (default: uses video_id)
    
    Returns:
    - Success message
    """
    try:
        conversation_memory.clear_history(video_id, session_id)
        return {
            "success": True,
            "message": f"Conversation history cleared for video: {video_id}, session: {session_id or 'default'}"
        }
    except Exception as e:
        logger.error(f"Error clearing conversation history: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error clearing conversation history: {str(e)}"
        )

@app.post("/api/qa/auto", response_model=QAResponse)
async def ask_question_auto(request: AutoQARequest):
    """
    Automatic Q&A endpoint - Fetches transcript automatically from YouTube with conversation memory
    
    Just provide video_id and question, and this endpoint will:
    1. Fetch the transcript from YouTube automatically
    2. Retrieve conversation history (if session_id provided)
    3. Send transcript + history + question to Azure OpenAI
    4. Store the Q&A exchange in memory
    5. Return the answer
    
    Request Body:
    - video_id: YouTube video ID (e.g., "UtXzdmpysmU")
    - question: User's question about the video
    - session_id: Optional session ID for conversation memory (default: uses video_id)
    - clear_history: Optional flag to clear conversation history (default: False)
    
    Returns:
    - success: Whether the request was successful
    - answer: AI-generated answer (if successful)
    - error: Error message (if failed)
    - video_id: Echo of the video ID
    - transcript_fetched: True (since transcript was auto-fetched)
    - session_id: Session ID used for this conversation
    - conversation_length: Number of Q&A exchanges in this conversation
    """
    try:
        # Validate Azure OpenAI is configured
        if not settings.validate():
            missing = settings.get_missing_settings()
            raise HTTPException(
                status_code=503,
                detail=f"Azure OpenAI is not configured. Missing: {', '.join(missing)}"
            )
        
        # Validate input
        if not request.video_id or not request.video_id.strip():
            raise HTTPException(
                status_code=400,
                detail="Video ID cannot be empty"
            )
        
        if not request.question or not request.question.strip():
            raise HTTPException(
                status_code=400,
                detail="Question cannot be empty"
            )
        
        logger.info(f"Processing automatic Q&A request for video: {request.video_id}")
        
        # Step 1: Fetch transcript from YouTube
        transcript_success, transcript, transcript_error = await YouTubeTranscriptService.get_transcript(
            request.video_id
        )
        
        if not transcript_success:
            logger.error(f"Failed to fetch transcript: {transcript_error}")
            raise HTTPException(
                status_code=404,
                detail=f"Could not fetch transcript: {transcript_error}"
            )
        
        logger.info(f"Transcript fetched successfully ({len(transcript)} characters)")
        logger.debug(f"Question: {request.question[:100]}...")
        
        # Step 2: Handle conversation memory
        if request.clear_history:
            conversation_memory.clear_history(request.video_id, request.session_id)
            logger.info(f"Cleared conversation history for video: {request.video_id}, session: {request.session_id}")
        
        # Get conversation history
        history = conversation_memory.get_history(request.video_id, request.session_id)
        formatted_history = conversation_memory.format_history_for_prompt(history) if history else None
        
        logger.info(f"Conversation history: {len(history)} previous exchanges")
        
        # Step 3: Get Azure OpenAI service
        try:
            azure_service = get_azure_service()
        except Exception as e:
            logger.error(f"Failed to get Azure service: {e}")
            raise HTTPException(
                status_code=503,
                detail=f"Azure OpenAI service unavailable: {str(e)}"
            )
        
        # Step 4: Call Azure OpenAI service with conversation history
        success, answer, error = await azure_service.ask_question(
            transcript=transcript,
            question=request.question,
            conversation_history=formatted_history
        )
        
        if success:
            # Store the exchange in conversation memory
            conversation_memory.add_exchange(
                video_id=request.video_id,
                question=request.question,
                answer=answer,
                session_id=request.session_id
            )
            
            # Get updated conversation length
            updated_history = conversation_memory.get_history(request.video_id, request.session_id)
            
            logger.info(f"Successfully generated answer for video: {request.video_id}")
            return QAResponse(
                success=True,
                answer=answer,
                error=None,
                video_id=request.video_id,
                transcript_fetched=True,
                session_id=request.session_id,
                conversation_length=len(updated_history)
            )
        else:
            logger.error(f"Azure OpenAI error for video {request.video_id}: {error}")
            raise HTTPException(
                status_code=500,
                detail=error or "Failed to get response from Azure OpenAI"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in /api/qa/auto: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@app.post("/api/qa", response_model=QAResponse)
async def ask_question(request: QARequest):
    """
    Manual Q&A endpoint - Requires transcript to be provided
    
    Use this if you already have the transcript (e.g., fetched client-side).
    For automatic transcript fetching, use /api/qa/auto instead.
    
    Request Body:
    - video_id: YouTube video ID
    - transcript: Full video transcript text
    - question: User's question about the video
    - session_id: Optional session ID for conversation memory
    - clear_history: Optional flag to clear conversation history (default: False)
    
    Returns:
    - success: Whether the request was successful
    - answer: AI-generated answer (if successful)
    - error: Error message (if failed)
    - video_id: Echo of the video ID
    - transcript_fetched: False (since transcript was provided)
    - session_id: Session ID used for this conversation
    - conversation_length: Number of Q&A exchanges in this conversation
    """
    try:
        # Validate Azure OpenAI is configured
        if not settings.validate():
            missing = settings.get_missing_settings()
            raise HTTPException(
                status_code=503,
                detail=f"Azure OpenAI is not configured. Missing: {', '.join(missing)}"
            )
        
        # Validate input
        if not request.transcript or not request.transcript.strip():
            raise HTTPException(
                status_code=400,
                detail="Transcript cannot be empty"
            )
        
        if not request.question or not request.question.strip():
            raise HTTPException(
                status_code=400,
                detail="Question cannot be empty"
            )
        
        logger.info(f"Processing Q&A request for video: {request.video_id}")
        logger.debug(f"Question: {request.question[:100]}...")
        logger.debug(f"Transcript length: {len(request.transcript)} characters")
        
        # Handle conversation memory
        if request.clear_history:
            conversation_memory.clear_history(request.video_id, request.session_id)
            logger.info(f"Cleared conversation history for video: {request.video_id}, session: {request.session_id}")
        
        # Get conversation history
        history = conversation_memory.get_history(request.video_id, request.session_id)
        formatted_history = conversation_memory.format_history_for_prompt(history) if history else None
        
        logger.info(f"Conversation history: {len(history)} previous exchanges")
        
        # Get Azure OpenAI service
        try:
            azure_service = get_azure_service()
        except Exception as e:
            logger.error(f"Failed to get Azure service: {e}")
            raise HTTPException(
                status_code=503,
                detail=f"Azure OpenAI service unavailable: {str(e)}"
            )
        
        # Call Azure OpenAI service with conversation history
        success, answer, error = await azure_service.ask_question(
            transcript=request.transcript,
            question=request.question,
            conversation_history=formatted_history
        )
        
        if success:
            # Store the exchange in conversation memory
            conversation_memory.add_exchange(
                video_id=request.video_id,
                question=request.question,
                answer=answer,
                session_id=request.session_id
            )
            
            # Get updated conversation length
            updated_history = conversation_memory.get_history(request.video_id, request.session_id)
            
            logger.info(f"Successfully generated answer for video: {request.video_id}")
            return QAResponse(
                success=True,
                answer=answer,
                error=None,
                video_id=request.video_id,
                transcript_fetched=False,
                session_id=request.session_id,
                conversation_length=len(updated_history)
            )
        else:
            logger.error(f"Azure OpenAI error for video {request.video_id}: {error}")
            raise HTTPException(
                status_code=500,
                detail=error or "Failed to get response from Azure OpenAI"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in /api/qa: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )