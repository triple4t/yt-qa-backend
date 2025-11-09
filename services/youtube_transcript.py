import httpx
from typing import Optional
import logging
import asyncio
from backend.config import settings
import re
import html

logger = logging.getLogger(__name__)

class YouTubeTranscriptService:
    """Service for fetching YouTube video transcripts using YouTube transcript API"""
    
    @staticmethod
    async def get_transcript(video_id: str, languages: list[str] = None) -> tuple[bool, Optional[str], Optional[str]]:
        """
        Fetch transcript using YouTube's transcript API endpoint
        This is the same endpoint that youtube-transcript-api uses, but we call it directly
        to avoid IP blocking issues with the library
        """
        if languages is None:
            languages = ['en', 'en-US', 'en-GB']
        
        try:
            logger.info(f"Fetching transcript for video: {video_id}")
            
            # Use YouTube's transcript API endpoint directly
            # This is the same endpoint that youtube-transcript-api uses
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                # Try each language
                transcript_text = None
                last_error = None
                
                for lang in languages:
                    try:
                        # YouTube transcript API endpoint
                        url = f"https://www.youtube.com/api/timedtext"
                        params = {
                            "v": video_id,
                            "lang": lang,
                            "fmt": "srv3"  # or "srv1", "srv2", "ttml", "vtt"
                        }
                        
                        response = await client.get(url, params=params)
                        
                        if response.status_code == 200:
                            # Parse XML/SRV format
                            transcript_text = YouTubeTranscriptService._parse_transcript_xml(response.text)
                            if transcript_text and transcript_text.strip():
                                logger.info(f"Found transcript in language: {lang}")
                                break
                    except Exception as e:
                        last_error = str(e)
                        logger.debug(f"Failed to fetch transcript in {lang}: {last_error}")
                        continue
                
                # If no preferred language worked, try without language parameter (auto-detect)
                if not transcript_text:
                    try:
                        url = f"https://www.youtube.com/api/timedtext"
                        params = {
                            "v": video_id,
                            "fmt": "srv3"
                        }
                        response = await client.get(url, params=params)
                        if response.status_code == 200:
                            transcript_text = YouTubeTranscriptService._parse_transcript_xml(response.text)
                            if transcript_text and transcript_text.strip():
                                logger.info("Found transcript (auto-detected language)")
                    except Exception as e:
                        last_error = str(e)
                
                if not transcript_text or not transcript_text.strip():
                    return False, None, f"No captions available for this video. {last_error if last_error else ''}"
                
                logger.info(f"Successfully fetched transcript ({len(transcript_text)} characters)")
                return True, transcript_text, None
                
        except httpx.TimeoutException:
            return False, None, "Request timeout while fetching transcript"
        except Exception as e:
            error_msg = f"Error fetching transcript: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, None, error_msg
    
    @staticmethod
    def _parse_transcript_xml(xml_content: str) -> str:
        """Parse YouTube transcript XML format and extract text"""
        # Remove XML tags and extract text
        # YouTube transcript XML format: <text start="..." dur="...">text content</text>
        text_pattern = r'<text[^>]*>(.*?)</text>'
        matches = re.findall(text_pattern, xml_content, re.DOTALL)
        
        # Clean up HTML entities and join
        text_lines = [html.unescape(match.strip()) for match in matches if match.strip()]
        
        return ' '.join(text_lines)