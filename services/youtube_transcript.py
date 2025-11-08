from langchain_community.document_loaders import YoutubeLoader
from typing import Optional
import logging
import asyncio

logger = logging.getLogger(__name__)

class YouTubeTranscriptService:
    """Service for fetching YouTube video transcripts using LangChain"""
    
    @staticmethod
    async def get_transcript(video_id: str, languages: list[str] = None) -> tuple[bool, Optional[str], Optional[str]]:
        """
        Fetch transcript for a YouTube video using LangChain's YoutubeLoader
        
        Args:
            video_id: YouTube video ID (e.g., "UtXzdmpysmU")
            languages: List of language codes to try (default: ['en'])
        
        Returns:
            tuple: (success: bool, transcript: Optional[str], error: Optional[str])
        """
        if languages is None:
            languages = ['en']
        
        try:
            logger.info(f"Fetching transcript for video: {video_id} using LangChain YoutubeLoader")
            
            # Construct YouTube URL from video ID
            youtube_url = f"https://www.youtube.com/watch?v={video_id}"
            
            # Run the synchronous LangChain loader in a thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            
            def load_transcript():
                """Load transcript using LangChain YoutubeLoader (same as main.py)"""
                try:
                    # Create loader exactly like in main.py
                    loader = YoutubeLoader.from_youtube_url(
                        youtube_url,
                        add_video_info=False,  # Set to False to avoid pytube dependency
                        language=languages,
                    )
                    
                    # Load documents
                    docs = loader.load()
                    
                    if not docs:
                        return None
                    
                    # Extract text from all documents and combine into single string
                    # Same approach as main.py but combine all docs
                    transcript_text = " ".join([doc.page_content for doc in docs])
                    return transcript_text
                    
                except Exception as e:
                    logger.error(f"LangChain YoutubeLoader error: {str(e)}")
                    raise
            
            # Execute in thread pool
            transcript_text = await loop.run_in_executor(None, load_transcript)
            
            if not transcript_text or not transcript_text.strip():
                return False, None, "Transcript is empty or could not be loaded"
            
            logger.info(f"Successfully fetched transcript ({len(transcript_text)} characters)")
            return True, transcript_text, None
            
        except Exception as e:
            error_msg = f"Error fetching transcript: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            # Provide more helpful error messages
            error_str = str(e).lower()
            if "transcript" in error_str and ("disabled" in error_str or "not available" in error_str):
                error_msg = f"Transcripts are disabled or not available for video: {video_id}"
            elif "video" in error_str and ("unavailable" in error_str or "private" in error_str or "deleted" in error_str):
                error_msg = f"Video is unavailable: {video_id}. The video may be private, deleted, or restricted."
            elif "language" in error_str or "not found" in error_str:
                error_msg = f"No transcript found for video: {video_id} in languages: {languages}. The video may not have captions enabled."
            elif "network" in error_str or "connection" in error_str or "timeout" in error_str:
                error_msg = f"Network error while fetching transcript: {str(e)}"
            elif "could not import" in error_str or "youtube_transcript_api" in error_str:
                error_msg = f"Missing dependency: youtube-transcript-api. Please install it with: pip install youtube-transcript-api"
            
            return False, None, error_msg