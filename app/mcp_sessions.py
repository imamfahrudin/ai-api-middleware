"""
MCP Session Management

This module handles session management for MCP tool interactions,
supporting multi-turn conversations with context preservation.
"""

import json
import time
import uuid
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

from app.database import KeyManager

logger = logging.getLogger(__name__)

class MCPSessionManager:
    """
    Manages MCP sessions for multi-turn conversations with context preservation
    """

    def __init__(self, key_manager: KeyManager):
        self.key_manager = key_manager
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        self.session_timeout = 3600  # 1 hour
        self.max_sessions = 1000
        self._cleanup_interval = 300  # 5 minutes
        self._last_cleanup = time.time()

    def create_session(self, user_context: Dict[str, Any], request_id: Optional[str] = None) -> str:
        """
        Create a new MCP session

        Args:
            user_context: Context information about the user/request
            request_id: Optional request identifier

        Returns:
            Session ID
        """
        try:
            session_id = request_id or str(uuid.uuid4())

            # Clean up expired sessions periodically
            self._cleanup_expired_sessions()

            # Check session limit
            if len(self.active_sessions) >= self.max_sessions:
                self._remove_oldest_session()

            # Create session
            session_data = {
                'session_id': session_id,
                'user_context': user_context,
                'conversation_history': [],
                'tool_context': {},
                'active_servers': set(),
                'created_at': time.time(),
                'last_activity': time.time(),
                'expires_at': time.time() + self.session_timeout,
                'request_count': 0,
                'tool_calls': [],
                'preferences': {
                    'max_tool_calls_per_request': 5,
                    'timeout': 30,
                    'enable_caching': True
                }
            }

            # Store in memory
            self.active_sessions[session_id] = session_data

            # Store in database
            self.key_manager._execute_query("""
                INSERT OR REPLACE INTO mcp_sessions
                (session_id, user_context, active_servers, created_at, last_activity, expires_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                json.dumps(user_context),
                json.dumps(list(session_data['active_servers'])),
                datetime.fromtimestamp(session_data['created_at']).isoformat(),
                datetime.fromtimestamp(session_data['last_activity']).isoformat(),
                datetime.fromtimestamp(session_data['expires_at']).isoformat()
            ))

            logger.info(f"Created MCP session: {session_id}")
            return session_id

        except Exception as e:
            logger.error(f"Error creating MCP session: {str(e)}")
            # Fallback: generate simple session ID
            return f"session_{int(time.time())}_{uuid.uuid4().hex[:8]}"

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session data

        Args:
            session_id: Session identifier

        Returns:
            Session data or None if not found/expired
        """
        try:
            # Check memory first
            if session_id in self.active_sessions:
                session = self.active_sessions[session_id]

                # Check if expired
                if time.time() > session['expires_at']:
                    self.remove_session(session_id)
                    return None

                # Update last activity
                session['last_activity'] = time.time()
                return session

            # Try to load from database
            session_data = self._load_session_from_db(session_id)
            if session_data:
                # Check if expired
                if time.time() > session_data['expires_at']:
                    self.remove_session(session_id)
                    return None

                # Load into memory
                self.active_sessions[session_id] = session_data
                session_data['last_activity'] = time.time()
                return session_data

            return None

        except Exception as e:
            logger.error(f"Error getting MCP session {session_id}: {str(e)}")
            return None

    def update_session(self, session_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update session data

        Args:
            session_id: Session identifier
            updates: Data to update

        Returns:
            True if successful, False otherwise
        """
        try:
            session = self.get_session(session_id)
            if not session:
                return False

            # Update session data
            for key, value in updates.items():
                if key in ['session_id', 'created_at']:
                    continue  # Don't allow updating these fields

                if key == 'active_servers' and isinstance(value, list):
                    session[key] = set(value)
                else:
                    session[key] = value

            session['last_activity'] = time.time()

            # Update in database
            self._save_session_to_db(session_id, session)

            logger.debug(f"Updated MCP session: {session_id}")
            return True

        except Exception as e:
            logger.error(f"Error updating MCP session {session_id}: {str(e)}")
            return False

    def add_conversation_turn(self, session_id: str, user_message: str,
                            ai_response: str, tool_results: List[Dict[str, Any]] = None,
                            metadata: Dict[str, Any] = None) -> bool:
        """
        Add a conversation turn to the session

        Args:
            session_id: Session identifier
            user_message: User's message
            ai_response: AI response
            tool_results: Tool results from this turn
            metadata: Additional metadata

        Returns:
            True if successful, False otherwise
        """
        try:
            session = self.get_session(session_id)
            if not session:
                return False

            # Create conversation turn
            turn = {
                'timestamp': time.time(),
                'user_message': user_message,
                'ai_response': ai_response,
                'tool_results': tool_results or [],
                'metadata': metadata or {},
                'turn_number': len(session['conversation_history']) + 1
            }

            # Add to conversation history
            session['conversation_history'].append(turn)
            session['request_count'] += 1

            # Update tool context
            if tool_results:
                for tool_result in tool_results:
                    if tool_result.get('success'):
                        tool_name = tool_result.get('tool_name')
                        server_id = tool_result.get('server_id')
                        result = tool_result.get('result')

                        # Store tool context for future reference
                        context_key = f"{server_id}:{tool_name}"
                        if context_key not in session['tool_context']:
                            session['tool_context'][context_key] = []

                        session['tool_context'][context_key].append({
                            'timestamp': time.time(),
                            'result': result,
                            'arguments': tool_result.get('arguments'),
                            'turn_number': turn['turn_number']
                        })

                        # Track active servers
                        if server_id:
                            session['active_servers'].add(server_id)

            # Update tool calls list
            if tool_results:
                session['tool_calls'].extend(tool_results)

            # Limit conversation history to prevent memory issues
            max_history = 50
            if len(session['conversation_history']) > max_history:
                session['conversation_history'] = session['conversation_history'][-max_history:]

            # Save session
            self._save_session_to_db(session_id, session)

            logger.debug(f"Added conversation turn to session {session_id}")
            return True

        except Exception as e:
            logger.error(f"Error adding conversation turn to session {session_id}: {str(e)}")
            return False

    def get_tool_context(self, session_id: str, tool_name: str = None,
                        server_id: str = None) -> List[Dict[str, Any]]:
        """
        Get tool context from previous turns

        Args:
            session_id: Session identifier
            tool_name: Optional tool name filter
            server_id: Optional server ID filter

        Returns:
            List of tool context entries
        """
        try:
            session = self.get_session(session_id)
            if not session:
                return []

            tool_context = session.get('tool_context', {})
            results = []

            for context_key, entries in tool_context.items():
                if tool_name or server_id:
                    key_server_id, key_tool_name = context_key.split(':', 1)

                    if tool_name and key_tool_name != tool_name:
                        continue
                    if server_id and key_server_id != str(server_id):
                        continue

                results.extend(entries)

            # Sort by timestamp (most recent first)
            results.sort(key=lambda x: x['timestamp'], reverse=True)

            return results

        except Exception as e:
            logger.error(f"Error getting tool context for session {session_id}: {str(e)}")
            return []

    def get_conversation_summary(self, session_id: str, max_turns: int = 10) -> Dict[str, Any]:
        """
        Get a summary of the conversation

        Args:
            session_id: Session identifier
            max_turns: Maximum number of recent turns to include

        Returns:
            Conversation summary
        """
        try:
            session = self.get_session(session_id)
            if not session:
                return {}

            conversation_history = session.get('conversation_history', [])
            recent_turns = conversation_history[-max_turns:] if conversation_history else []

            # Extract key information
            tool_usage = {}
            topics = []

            for turn in recent_turns:
                # Analyze tool usage
                for tool_result in turn.get('tool_results', []):
                    tool_name = tool_result.get('tool_name', 'unknown')
                    tool_usage[tool_name] = tool_usage.get(tool_name, 0) + 1

                # Extract potential topics (simple keyword extraction)
                user_msg = turn.get('user_message', '').lower()
                if len(user_msg) > 10:  # Only meaningful messages
                    # Simple topic extraction - in production, use NLP
                    words = user_msg.split()
                    topics.extend([word for word in words if len(word) > 4])

            return {
                'session_id': session_id,
                'total_turns': len(conversation_history),
                'recent_turns': recent_turns,
                'tool_usage': tool_usage,
                'topics': list(set(topics))[:10],  # Top 10 unique topics
                'active_servers': list(session.get('active_servers', set())),
                'session_duration': time.time() - session.get('created_at', time.time()),
                'last_activity': session.get('last_activity')
            }

        except Exception as e:
            logger.error(f"Error getting conversation summary for session {session_id}: {str(e)}")
            return {}

    def remove_session(self, session_id: str) -> bool:
        """
        Remove a session

        Args:
            session_id: Session identifier

        Returns:
            True if successful, False otherwise
        """
        try:
            # Remove from memory
            if session_id in self.active_sessions:
                del self.active_sessions[session_id]

            # Remove from database
            self.key_manager._execute_query(
                "DELETE FROM mcp_sessions WHERE session_id = ?",
                (session_id,)
            )

            logger.info(f"Removed MCP session: {session_id}")
            return True

        except Exception as e:
            logger.error(f"Error removing MCP session {session_id}: {str(e)}")
            return False

    def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired sessions

        Returns:
            Number of sessions removed
        """
        try:
            current_time = time.time()
            expired_sessions = []

            for session_id, session in list(self.active_sessions.items()):
                if current_time > session['expires_at']:
                    expired_sessions.append(session_id)

            # Remove expired sessions
            for session_id in expired_sessions:
                self.remove_session(session_id)

            # Also cleanup from database
            expired_timestamp = datetime.fromtimestamp(current_time).isoformat()
            self.key_manager._execute_query(
                "DELETE FROM mcp_sessions WHERE expires_at < ?",
                (expired_timestamp,)
            )

            logger.info(f"Cleaned up {len(expired_sessions)} expired MCP sessions")
            return len(expired_sessions)

        except Exception as e:
            logger.error(f"Error cleaning up expired MCP sessions: {str(e)}")
            return 0

    def get_session_stats(self) -> Dict[str, Any]:
        """
        Get session statistics

        Returns:
            Session statistics
        """
        try:
            current_time = time.time()
            active_count = len(self.active_sessions)

            # Calculate ages
            ages = []
            for session in self.active_sessions.values():
                age = current_time - session['created_at']
                ages.append(age)

            # Tool usage stats
            total_tool_calls = sum(len(session.get('tool_calls', [])) for session in self.active_sessions.values())

            return {
                'active_sessions': active_count,
                'max_sessions': self.max_sessions,
                'average_session_age': sum(ages) / len(ages) if ages else 0,
                'oldest_session_age': max(ages) if ages else 0,
                'total_tool_calls': total_tool_calls,
                'average_tool_calls_per_session': total_tool_calls / active_count if active_count > 0 else 0
            }

        except Exception as e:
            logger.error(f"Error getting session stats: {str(e)}")
            return {'error': str(e)}

    def _load_session_from_db(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load session from database"""
        try:
            cursor = self.key_manager.conn.cursor()
            cursor.execute("""
                SELECT session_id, user_context, active_servers, created_at,
                       last_activity, expires_at
                FROM mcp_sessions
                WHERE session_id = ?
            """, (session_id,))

            row = cursor.fetchone()
            if not row:
                return None

            # Convert database row to session format
            session = {
                'session_id': row['session_id'],
                'user_context': json.loads(row['user_context']) if row['user_context'] else {},
                'active_servers': set(json.loads(row['active_servers'])) if row['active_servers'] else set(),
                'created_at': datetime.fromisoformat(row['created_at']).timestamp(),
                'last_activity': datetime.fromisoformat(row['last_activity']).timestamp(),
                'expires_at': datetime.fromisoformat(row['expires_at']).timestamp(),
                'conversation_history': [],
                'tool_context': {},
                'request_count': 0,
                'tool_calls': [],
                'preferences': {
                    'max_tool_calls_per_request': 5,
                    'timeout': 30,
                    'enable_caching': True
                }
            }

            return session

        except Exception as e:
            logger.error(f"Error loading session from DB {session_id}: {str(e)}")
            return None

    def _save_session_to_db(self, session_id: str, session_data: Dict[str, Any]):
        """Save session to database"""
        try:
            self.key_manager._execute_query("""
                INSERT OR REPLACE INTO mcp_sessions
                (session_id, user_context, active_servers, created_at, last_activity, expires_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                json.dumps(session_data.get('user_context', {})),
                json.dumps(list(session_data.get('active_servers', []))),
                datetime.fromtimestamp(session_data['created_at']).isoformat(),
                datetime.fromtimestamp(session_data['last_activity']).isoformat(),
                datetime.fromtimestamp(session_data['expires_at']).isoformat()
            ))

        except Exception as e:
            logger.error(f"Error saving session to DB {session_id}: {str(e)}")

    def _cleanup_expired_sessions(self):
        """Periodic cleanup of expired sessions"""
        current_time = time.time()
        if current_time - self._last_cleanup < self._cleanup_interval:
            return

        self.cleanup_expired_sessions()
        self._last_cleanup = current_time

    def _remove_oldest_session(self):
        """Remove the oldest session when limit is reached"""
        try:
            if not self.active_sessions:
                return

            # Find oldest session
            oldest_session_id = min(
                self.active_sessions.keys(),
                key=lambda sid: self.active_sessions[sid]['created_at']
            )

            self.remove_session(oldest_session_id)
            logger.info(f"Removed oldest session due to limit: {oldest_session_id}")

        except Exception as e:
            logger.error(f"Error removing oldest session: {str(e)}")

# Global session manager instance
mcp_session_manager: Optional[MCPSessionManager] = None

def initialize_mcp_sessions(key_manager: KeyManager):
    """Initialize MCP session manager"""
    global mcp_session_manager
    mcp_session_manager = MCPSessionManager(key_manager)

def get_mcp_session_manager() -> Optional[MCPSessionManager]:
    """Get global MCP session manager"""
    return mcp_session_manager