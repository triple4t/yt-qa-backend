import httpx
from typing import Optional
import logging
import asyncio
from config import settings  # Fixed import
import re
import html

logger = logging.getLogger(__name__)
class YouTubeTranscriptService:
    """Service for fetching YouTube video transcripts using YouTube transcript API"""
    
    @staticmethod
    async def get_transcript(video_id: str, languages: list[str] = None) -> tuple[bool, Optional[str], Optional[str]]:
        """
        Fetch transcript using YouTube's transcript API endpoint
        Try just one format/language first to avoid rate limiting
        """
        if languages is None:
            languages = ['en', 'en-US', 'en-GB']
        
        try:
            logger.info(f"Fetching transcript for video: {video_id}")
            
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                # Try just ONE format first (srv3 is most common)
                url = f"https://www.youtube.com/api/timedtext"
                
                # Try languages in order, one at a time
                for lang in languages:
                    try:
                        params = {
                            "v": video_id,
                            "lang": lang,
                            "fmt": "srv3"
                        }
                        
                        response = await client.get(url, params=params)
                        
                        # If rate limited, stop immediately
                        if response.status_code == 429:
                            logger.warning(f"Rate limited by YouTube. Azure IP is blocked.")
                            return False, None, "YouTube is rate limiting requests from this server. This is common with cloud provider IPs. Please wait a few minutes or use a different server."
                        
                        logger.info(f"Response status ({lang}): {response.status_code}, length: {len(response.text) if response.text else 0}")
                        
                        if response.status_code == 200 and response.text and len(response.text.strip()) > 0:
                            logger.info(f"Response preview: {response.text[:300]}")
                            
                            transcript_text = YouTubeTranscriptService._parse_transcript_xml(response.text)
                            
                            if transcript_text and transcript_text.strip():
                                logger.info(f"Found transcript in language: {lang}")
                                return True, transcript_text, None
                    except Exception as e:
                        logger.debug(f"Failed ({lang}): {str(e)}")
                        continue
                
                # If no language worked, try without language (auto-detect) - ONE attempt only
                try:
                    params = {"v": video_id, "fmt": "srv3"}
                    response = await client.get(url, params=params)
                    
                    if response.status_code == 429:
                        return False, None, "YouTube is rate limiting requests from this server. This is common with cloud provider IPs."
                    
                    if response.status_code == 200 and response.text:
                        transcript_text = YouTubeTranscriptService._parse_transcript_xml(response.text)
                        if transcript_text and transcript_text.strip():
                            logger.info("Found transcript (auto-detected)")
                            return True, transcript_text, None
                except Exception as e:
                    logger.debug(f"Auto-detect failed: {str(e)}")
                
                return False, None, "No captions available for this video or YouTube is blocking requests."
                
        except httpx.TimeoutException:
            return False, None, "Request timeout while fetching transcript"
        except Exception as e:
            error_msg = f"Error fetching transcript: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, None, error_msg
    
    @staticmethod
    def _parse_transcript_xml(xml_content: str) -> str:
        """Parse YouTube transcript XML format and extract text"""
        # Try multiple patterns for different XML structures
        text_lines = []
        
        # Pattern 1: <text start="..." dur="...">text content</text>
        pattern1 = r'<text[^>]*>(.*?)</text>'
        matches1 = re.findall(pattern1, xml_content, re.DOTALL)
        if matches1:
            text_lines.extend([html.unescape(match.strip()) for match in matches1 if match.strip()])
        
        # Pattern 2: <p t="..." d="...">text content</p>
        pattern2 = r'<p[^>]*>(.*?)</p>'
        matches2 = re.findall(pattern2, xml_content, re.DOTALL)
        if matches2:
            text_lines.extend([html.unescape(match.strip()) for match in matches2 if match.strip()])
        
        # Pattern 3: Just extract all text between tags
        if not text_lines:
            # Remove all XML tags and get remaining text
            text = re.sub(r'<[^>]+>', ' ', xml_content)
            text = html.unescape(text)
            text_lines = [line.strip() for line in text.split() if line.strip()]
        
        return ' '.join(text_lines)
    
    @staticmethod
    def _parse_vtt(vtt_content: str) -> str:
        """Parse WebVTT format"""
        lines = vtt_content.split('\n')
        text_lines = []
        
        for line in lines:
            line = line.strip()
            # Skip VTT headers, timestamps, and empty lines
            if not line or line.startswith('WEBVTT') or '-->' in line or line.isdigit():
                continue
            # Skip style/note blocks
            if line.startswith('NOTE') or line.startswith('STYLE'):
                continue
            text_lines.append(line)
        
        return ' '.join(text_lines)
    
    @staticmethod
    def _parse_ttml(ttml_content: str) -> str:
        """Parse TTML format"""
        # Extract text from <p> tags in TTML
        pattern = r'<p[^>]*>(.*?)</p>'
        matches = re.findall(pattern, ttml_content, re.DOTALL)
        text_lines = [html.unescape(match.strip()) for match in matches if match.strip()]
        return ' '.join(text_lines)