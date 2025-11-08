import httpx
from typing import Optional
from config import settings
import logging

logger = logging.getLogger(__name__)

class AzureOpenAIService:
    """Service for interacting with Azure OpenAI API"""
    
    def __init__(self):
        if not settings.validate():
            missing = settings.get_missing_settings()
            raise ValueError(
                f"Azure OpenAI settings are not properly configured. "
                f"Missing: {', '.join(missing)}"
            )
        
        self.api_key = settings.AZURE_OPENAI_API_KEY
        self.api_url = settings.azure_openai_url
        self.api_version = settings.AZURE_OPENAI_API_VERSION
        logger.info(f"Azure OpenAI service initialized with endpoint: {settings.AZURE_OPENAI_ENDPOINT}")
    
    async def ask_question(
        self, 
        transcript: str, 
        question: str,
        conversation_history: Optional[str] = None
    ) -> tuple[bool, Optional[str], Optional[str]]:
        """
        Ask a question about the transcript using Azure OpenAI
        
        Args:
            transcript: The full video transcript text
            question: The user's question
            conversation_history: Optional formatted conversation history
        
        Returns:
            tuple: (success: bool, answer: Optional[str], error: Optional[str])
        """
        try:
            # Build the user content with optional conversation history
            # Don't label it as "transcript" - make it feel like video content
            user_content = f"Video Content:\n\n{transcript}\n\n"
            
            if conversation_history:
                user_content += conversation_history + "\n\n"
            
            user_content += f"Question: {question}"
            
            # Construct the system and user messages for RAG
            system_message = (
                "You are an expert Q&A assistant for video content. "
                "You analyze video content and provide helpful, accurate, and engaging answers. "
                "Always be conversational, natural, and helpful. "
                "IMPORTANT: Never mention 'transcript', 'transcription', 'captions', or any technical details about how you access the content. "
                "Act as if you are directly watching and analyzing the video. "
                "Use phrases like 'in this video', 'the speaker mentions', 'the video discusses', 'as shown in the video', etc. "
            )
            
            if conversation_history:
                system_message += (
                    "You have access to previous questions and answers in this conversation. "
                    "Use this context to provide better answers, especially for follow-up questions. "
                    "If the current question refers to something from the previous conversation, "
                    "you can reference it naturally. "
                )
            
            system_message += (
                "When answering questions:\n"
                "- Base your answers on what is discussed in the video\n"
                "- If specific details aren't mentioned, provide a helpful response based on what IS discussed\n"
                "- Never say phrases like 'not provided', 'not mentioned', 'details are not provided', 'not in the transcript', or 'the transcript doesn't mention'\n"
                "- Instead, offer related information from the video or explain what the video does cover on that topic\n"
                "- Be conversational and helpful - focus on what the video DOES discuss rather than what it doesn't\n"
                "- If asked about something completely unrelated to the video content, politely redirect to what the video is actually about\n"
                "- Always speak as if you watched the video yourself - use natural language like 'In this video, the speaker explains...' or 'The video covers...'"
            )
            
            messages = [
                {
                    "role": "system",
                    "content": system_message
                },
                {
                    "role": "user",
                    "content": user_content
                }
            ]
            
            # Prepare the request payload
            payload = {
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 1000,
                "top_p": 0.95,
                "frequency_penalty": 0,
                "presence_penalty": 0
            }
            
            logger.info(f"Calling Azure OpenAI API: {self.api_url}")
            
            # Make the API call with extended timeout for long transcripts
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.api_url}?api-version={self.api_version}",
                    headers={
                        "Content-Type": "application/json",
                        "api-key": self.api_key
                    },
                    json=payload
                )
                
                # Handle response
                if response.status_code == 200:
                    data = response.json()
                    choices = data.get("choices", [])
                    
                    if not choices:
                        return False, None, "No choices returned from Azure OpenAI"
                    
                    answer = choices[0].get("message", {}).get("content", "")
                    
                    if not answer:
                        return False, None, "No response content from Azure OpenAI"
                    
                    logger.info("Successfully received response from Azure OpenAI")
                    return True, answer, None
                
                else:
                    error_msg = f"Azure OpenAI API error: {response.status_code}"
                    try:
                        error_data = response.json()
                        error_detail = error_data.get("error", {})
                        error_msg += f" - {error_detail.get('message', 'Unknown error')}"
                        if "code" in error_detail:
                            error_msg += f" (Code: {error_detail['code']})"
                    except:
                        error_msg += f" - {response.text[:200]}"
                    
                    logger.error(f"Azure OpenAI API error: {error_msg}")
                    return False, None, error_msg
                    
        except httpx.TimeoutException:
            error_msg = "Request timeout: Azure OpenAI API took too long to respond"
            logger.error(error_msg)
            return False, None, error_msg
        except httpx.RequestError as e:
            error_msg = f"Network error: {str(e)}"
            logger.error(error_msg)
            return False, None, error_msg
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, None, error_msg

# Global service instance (will be initialized on first import)
azure_openai_service = None

def get_azure_service() -> AzureOpenAIService:
    """Get or create the Azure OpenAI service instance"""
    global azure_openai_service
    if azure_openai_service is None:
        azure_openai_service = AzureOpenAIService()
    return azure_openai_service