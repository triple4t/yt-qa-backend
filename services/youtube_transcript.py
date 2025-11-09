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
        This is the same endpoint that youtube-transcript-api uses, but we call it directly
        to avoid IP blocking issues with the library
        """
        if languages is None:
            languages = ['en', 'en-US', 'en-GB']
        
        try:
            logger.info(f"Fetching transcript for video: {video_id}")
            
            # Use YouTube's transcript API endpoint directly
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                # Try different formats
                formats = ["srv3", "srv1", "srv2", "vtt", "ttml"]
                transcript_text = None
                last_error = None
                
                for fmt in formats:
                    for lang in languages:
                        try:
                            url = f"https://www.youtube.com/api/timedtext"
                            params = {
                                "v": video_id,
                                "lang": lang,
                                "fmt": fmt
                            }
                            
                            response = await client.get(url, params=params)
                            
                            logger.info(f"Response status ({fmt}, {lang}): {response.status_code}, content-type: {response.headers.get('content-type', 'unknown')}, text length: {len(response.text) if response.text else 0}")
                            
                            if response.status_code == 200 and response.text and len(response.text.strip()) > 0:
                                # Log response details at INFO level
                                logger.info(f"Response preview ({fmt}, {lang}): {response.text[:500]}")
                                
                                # Parse based on format
                                if fmt in ["srv3", "srv1", "srv2"]:
                                    transcript_text = YouTubeTranscriptService._parse_transcript_xml(response.text)
                                elif fmt == "vtt":
                                    transcript_text = YouTubeTranscriptService._parse_vtt(response.text)
                                elif fmt == "ttml":
                                    transcript_text = YouTubeTranscriptService._parse_ttml(response.text)
                                
                                logger.info(f"Parsed text length: {len(transcript_text) if transcript_text else 0}, preview: {transcript_text[:200] if transcript_text else 'None'}")
                                
                                if transcript_text and transcript_text.strip():
                                    logger.info(f"Found transcript in language: {lang}, format: {fmt}")
                                    return True, transcript_text, None
                            else:
                                logger.warning(f"Empty or invalid response ({fmt}, {lang}): status={response.status_code}, text_length={len(response.text) if response.text else 0}")
                        except Exception as e:
                            last_error = str(e)
                            logger.debug(f"Failed to fetch transcript ({fmt}, {lang}): {last_error}")
                            continue
                
                # If no preferred language worked, try without language parameter (auto-detect)
                if not transcript_text:
                    for fmt in formats:
                        try:
                            url = f"https://www.youtube.com/api/timedtext"
                            params = {
                                "v": video_id,
                                "fmt": fmt
                            }
                            response = await client.get(url, params=params)
                            if response.status_code == 200 and response.text:
                                logger.debug(f"Response preview ({fmt}, auto): {response.text[:200]}")
                                
                                if fmt in ["srv3", "srv1", "srv2"]:
                                    transcript_text = YouTubeTranscriptService._parse_transcript_xml(response.text)
                                elif fmt == "vtt":
                                    transcript_text = YouTubeTranscriptService._parse_vtt(response.text)
                                elif fmt == "ttml":
                                    transcript_text = YouTubeTranscriptService._parse_ttml(response.text)
                                
                                if transcript_text and transcript_text.strip():
                                    logger.info(f"Found transcript (auto-detected language), format: {fmt}")
                                    return True, transcript_text, None
                        except Exception as e:
                            last_error = str(e)
                            continue
                
                if not transcript_text or not transcript_text.strip():
                    return False, None, f"No captions available for this video. {last_error if last_error else 'Response was empty or could not be parsed.'}"
                
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