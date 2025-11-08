from typing import Optional, List, Dict
from datetime import datetime, timedelta
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

class ConversationMemory:
    """Manages conversation history for Q&A sessions"""
    
    def __init__(self, max_history: int = 10, ttl_hours: int = 24):
        """
        Initialize conversation memory
        
        Args:
            max_history: Maximum number of Q&A pairs to keep in memory
            ttl_hours: Time to live for conversations in hours
        """
        self.conversations: Dict[str, List[Dict]] = defaultdict(list)
        self.timestamps: Dict[str, datetime] = {}
        self.max_history = max_history
        self.ttl_hours = ttl_hours
    
    def _get_session_key(self, video_id: str, session_id: Optional[str] = None) -> str:
        """Generate a unique session key"""
        if session_id:
            return f"{video_id}:{session_id}"
        return f"{video_id}:default"
    
    def _cleanup_expired(self):
        """Remove expired conversations"""
        now = datetime.now()
        expired_keys = [
            key for key, timestamp in self.timestamps.items()
            if now - timestamp > timedelta(hours=self.ttl_hours)
        ]
        for key in expired_keys:
            del self.conversations[key]
            del self.timestamps[key]
            logger.info(f"Cleaned up expired conversation: {key}")
    
    def add_exchange(
        self, 
        video_id: str, 
        question: str, 
        answer: str, 
        session_id: Optional[str] = None
    ):
        """
        Add a Q&A exchange to conversation history
        
        Args:
            video_id: YouTube video ID
            question: User's question
            answer: AI's answer
            session_id: Optional session ID for multi-user support
        """
        self._cleanup_expired()
        
        session_key = self._get_session_key(video_id, session_id)
        
        # Add the exchange
        self.conversations[session_key].append({
            "question": question,
            "answer": answer,
            "timestamp": datetime.now().isoformat()
        })
        
        # Limit history size
        if len(self.conversations[session_key]) > self.max_history:
            self.conversations[session_key] = self.conversations[session_key][-self.max_history:]
        
        # Update timestamp
        self.timestamps[session_key] = datetime.now()
        
        logger.info(f"Added exchange to conversation {session_key} (total: {len(self.conversations[session_key])})")
    
    def get_history(
        self, 
        video_id: str, 
        session_id: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """
        Get conversation history for a session
        
        Args:
            video_id: YouTube video ID
            session_id: Optional session ID
            limit: Optional limit on number of exchanges to return
        
        Returns:
            List of Q&A exchanges
        """
        self._cleanup_expired()
        
        session_key = self._get_session_key(video_id, session_id)
        history = self.conversations.get(session_key, [])
        
        if limit:
            return history[-limit:]
        return history
    
    def clear_history(self, video_id: str, session_id: Optional[str] = None):
        """Clear conversation history for a session"""
        session_key = self._get_session_key(video_id, session_id)
        if session_key in self.conversations:
            del self.conversations[session_key]
        if session_key in self.timestamps:
            del self.timestamps[session_key]
        logger.info(f"Cleared conversation history for {session_key}")
    
    def format_history_for_prompt(self, history: List[Dict]) -> str:
        """
        Format conversation history for inclusion in prompt
        
        Args:
            history: List of Q&A exchanges
        
        Returns:
            Formatted string of conversation history
        """
        if not history:
            return ""
        
        formatted = "\n\nPrevious conversation:\n"
        for i, exchange in enumerate(history, 1):
            formatted += f"\nQ{i}: {exchange['question']}\n"
            formatted += f"A{i}: {exchange['answer']}\n"
        
        return formatted

# Global conversation memory instance
conversation_memory = ConversationMemory(max_history=10, ttl_hours=24)

