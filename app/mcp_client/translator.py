"""
MCP Request Translation Layer

This module provides intelligent detection of when AI requests need MCP tools
and translates between standard AI API requests and MCP tool calls.
"""

import re
import json
import logging
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)

class MCPIntentDetector:
    """
    Detects when AI requests need MCP tools and identifies which tools would be helpful
    """

    def __init__(self, tool_manager):
        self.tool_manager = tool_manager
        self.intent_patterns = self._initialize_intent_patterns()
        self.tool_keywords = self._initialize_tool_keywords()

    def _initialize_intent_patterns(self) -> Dict[str, List[re.Pattern]]:
        """Initialize regex patterns for different types of tool needs"""
        return {
            'weather': [
                re.compile(r'\b(weather|temperature|forecast|rain|sunny|cloudy|wind)\b', re.IGNORECASE),
                re.compile(r'\b(what(?:\'| i)s)?\s+the\s+weather\b', re.IGNORECASE),
                re.compile(r'\b(how\s+(?:hot|cold|warm)|temperature)\s+in\b', re.IGNORECASE),
            ],
            'search': [
                re.compile(r'\b(search|find|look\s+up|google|web)\b', re.IGNORECASE),
                re.compile(r'\b(what\s+is|who\s+is|when\s+was|where\s+is)\b', re.IGNORECASE),
                re.compile(r'\b(tell\s+me\s+about|information\s+on|details\s+about)\b', re.IGNORECASE),
            ],
            'calculation': [
                re.compile(r'\b(calculate|compute|solve|math|add|subtract|multiply|divide)\b', re.IGNORECASE),
                re.compile(r'\b\d+\s*[\+\-\*\/]\s*\d+\b'),  # Simple math expressions
                re.compile(r'\b(what\s+is|equals?)\s*\d+', re.IGNORECASE),
            ],
            'data_access': [
                re.compile(r'\b(get|fetch|retrieve|load|access)\s+(?:data|information|records?)\b', re.IGNORECASE),
                re.compile(r'\b(database|table|records?|files?)\b', re.IGNORECASE),
            ],
            'time': [
                re.compile(r'\b(current\s+time|what\s+time|time\s+zone|date|today|now)\b', re.IGNORECASE),
            ]
        }

    def _initialize_tool_keywords(self) -> Dict[str, List[str]]:
        """Initialize keyword mappings for tools"""
        return {
            'get_weather': ['weather', 'temperature', 'forecast', 'rain', 'sunny', 'climate'],
            'search_web': ['search', 'find', 'lookup', 'google', 'web', 'information', 'news'],
            'calculate': ['calculate', 'compute', 'math', 'add', 'subtract', 'multiply', 'divide', 'equals'],
            'get_current_time': ['time', 'clock', 'hour', 'minute', 'current time'],
            'get_database_records': ['database', 'records', 'data', 'table', 'query'],
            'send_email': ['email', 'mail', 'send', 'message'],
            'create_file': ['create', 'file', 'write', 'save'],
            'read_file': ['read', 'file', 'open', 'load'],
        }

    def analyze_request(self, request_text: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Analyze if request needs MCP tools

        Args:
            request_text: The user's request text
            context: Additional context information

        Returns:
            Analysis result with tool recommendations
        """
        try:
            request_lower = request_text.lower()

            # Detect intent types
            detected_intents = []
            intent_matches = defaultdict(list)

            for intent_type, patterns in self.intent_patterns.items():
                for pattern in patterns:
                    matches = pattern.findall(request_text)
                    if matches:
                        detected_intents.append(intent_type)
                        intent_matches[intent_type].extend(matches)

            # Find specific tools that could help
            tool_recommendations = self._find_matching_tools(request_text, detected_intents)

            # Calculate confidence scores
            confidence_scores = self._calculate_confidence_scores(
                request_text, detected_intents, tool_recommendations
            )

            # Extract potential tool arguments
            extracted_arguments = self._extract_tool_arguments(
                request_text, tool_recommendations, detected_intents
            )

            result = {
                'requires_tools': len(tool_recommendations) > 0,
                'detected_intents': detected_intents,
                'intent_matches': dict(intent_matches),
                'recommended_tools': tool_recommendations,
                'confidence_scores': confidence_scores,
                'extracted_arguments': extracted_arguments,
                'analysis_timestamp': asyncio.get_event_loop().time()
            }

            logger.debug(f"Intent analysis result: {result}")
            return result

        except Exception as e:
            logger.error(f"Error in intent analysis: {str(e)}")
            return {
                'requires_tools': False,
                'error': str(e),
                'detected_intents': [],
                'recommended_tools': []
            }

    def _find_matching_tools(self, request_text: str, detected_intents: List[str]) -> List[Dict[str, Any]]:
        """Find tools that match the request"""
        request_lower = request_text.lower()
        matching_tools = []

        # Get all available tools
        all_tools = []
        for tool_key, metadata in self.tool_manager.tool_metadata.items():
            all_tools.append({
                'tool_key': tool_key,
                'name': metadata['tool_name'],
                'description': metadata['description'],
                'capabilities': metadata['capabilities'],
                'category': metadata['category'],
                'server_id': metadata['server_id']
            })

        # Score tools based on keyword matching
        for tool in all_tools:
            score = 0
            reasons = []

            # Check tool name and description
            tool_text = f"{tool['name']} {tool['description'] or ''}".lower()
            keyword_score = self._calculate_keyword_score(request_lower, tool_text)
            score += keyword_score
            if keyword_score > 0:
                reasons.append(f"keyword match: {keyword_score}")

            # Check capabilities
            for capability in tool['capabilities']:
                if capability in detected_intents:
                    score += 2
                    reasons.append(f"capability match: {capability}")

            # Check category
            if tool['category'] in detected_intents:
                score += 1.5
                reasons.append(f"category match: {tool['category']}")

            # Only include tools with meaningful scores
            if score >= 1:
                matching_tools.append({
                    **tool,
                    'match_score': score,
                    'match_reasons': reasons
                })

        # Sort by score and return top matches
        matching_tools.sort(key=lambda x: x['match_score'], reverse=True)
        return matching_tools[:5]  # Return top 5 matches

    def _calculate_keyword_score(self, request_text: str, tool_text: str) -> float:
        """Calculate keyword matching score"""
        score = 0
        request_words = set(request_text.split())
        tool_words = set(tool_text.split())

        # Exact word matches
        exact_matches = request_words.intersection(tool_words)
        score += len(exact_matches) * 2

        # Partial matches
        for req_word in request_words:
            for tool_word in tool_words:
                if req_word in tool_word or tool_word in req_word:
                    if len(req_word) > 3 and len(tool_word) > 3:  # Only count meaningful words
                        score += 0.5

        return score

    def _calculate_confidence_scores(self, request_text: str, detected_intents: List[str],
                                   tool_recommendations: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calculate confidence scores for different aspects"""
        scores = {}

        # Overall tool confidence
        if tool_recommendations:
            top_score = tool_recommendations[0]['match_score']
            scores['overall'] = min(top_score / 5, 1.0)  # Normalize to 0-1
        else:
            scores['overall'] = 0.0

        # Intent confidence
        if detected_intents:
            scores['intent'] = len(detected_intents) / len(self.intent_patterns)
        else:
            scores['intent'] = 0.0

        # Specific tool confidences
        for tool in tool_recommendations[:3]:  # Top 3 tools
            tool_name = tool['name']
            scores[tool_name] = min(tool['match_score'] / 5, 1.0)

        return scores

    def _extract_tool_arguments(self, request_text: str, tool_recommendations: List[Dict[str, Any]],
                              detected_intents: List[str]) -> Dict[str, Any]:
        """Extract potential arguments for tools from request text"""
        arguments = {}

        for tool in tool_recommendations[:3]:  # Extract for top 3 tools
            tool_name = tool['name']
            tool_args = {}

            # Weather tool arguments
            if tool_name == 'get_weather':
                location = self._extract_location(request_text)
                if location:
                    tool_args['location'] = location

                units = self._extract_temperature_units(request_text)
                if units:
                    tool_args['units'] = units

            # Search tool arguments
            elif tool_name == 'search_web':
                query = self._extract_search_query(request_text)
                if query:
                    tool_args['query'] = query

            # Calculation tool arguments
            elif tool_name == 'calculate':
                expression = self._extract_math_expression(request_text)
                if expression:
                    tool_args['expression'] = expression

            if tool_args:
                arguments[tool_name] = tool_args

        return arguments

    def _extract_location(self, text: str) -> Optional[str]:
        """Extract location from text"""
        # Simple location extraction - in production, use NER or more sophisticated methods
        location_patterns = [
            r'\b(in|at|for)\s+([A-Z][a-z\s]+)(?:\?|\.|$)',  # "in New York"
            r'\b([A-Z][a-z\s]+)\s+weather\b',  # "New York weather"
        ]

        for pattern in location_patterns:
            match = re.search(pattern, text)
            if match:
                location = match.group(2) if match.groups() else match.group(1)
                if len(location.strip()) > 2:
                    return location.strip()

        return None

    def _extract_temperature_units(self, text: str) -> Optional[str]:
        """Extract temperature units from text"""
        if re.search(r'\b(celsius|°c|c)\b', text, re.IGNORECASE):
            return 'celsius'
        elif re.search(r'\b(fahrenheit|°f|f)\b', text, re.IGNORECASE):
            return 'fahrenheit'
        return None

    def _extract_search_query(self, text: str) -> Optional[str]:
        """Extract search query from text"""
        # Look for phrases that indicate search queries
        search_patterns = [
            r'(?:search|find|look\s+up)\s+(?:for\s+)?["\']?(.+?)["\']?(?:\?|\.|$)',
            r'(?:what|who|when|where|how)\s+(?:is|are|was|were)\s+(.+?)(?:\?|\.|$)',
            r'tell\s+me\s+(?:about|more\s+about)\s+(.+?)(?:\?|\.|$)',
        ]

        for pattern in search_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                query = match.group(1).strip()
                if len(query) > 3:
                    return query

        return None

    def _extract_math_expression(self, text: str) -> Optional[str]:
        """Extract math expression from text"""
        # Look for math expressions
        math_patterns = [
            r'(\d+(?:\.\d+)?\s*[\+\-\*\/]\s*\d+(?:\.\d+)?)',  # Basic arithmetic
            r'(?:calculate|compute|what\s+is)\s+(.+?)(?:\?|\.|$)',  # "calculate 2+2"
        ]

        for pattern in math_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                expression = match.group(1).strip()
                # Basic validation
                if re.search(r'[\d\+\-\*\/\(\)\s\.]+', expression):
                    return expression

        return None

class MCPRequestTranslator:
    """
    Translates standard AI requests into MCP tool calls
    """

    def __init__(self, intent_detector: MCPIntentDetector, tool_manager):
        self.intent_detector = intent_detector
        self.tool_manager = tool_manager

    def translate_to_mcp_request(self, original_request: str, detected_tools: List[Dict[str, Any]],
                               extracted_arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert standard AI request to MCP tool calls

        Args:
            original_request: Original user request
            detected_tools: List of recommended tools
            extracted_arguments: Extracted arguments for tools

        Returns:
            MCP request structure
        """
        try:
            tool_calls = []

            for tool in detected_tools:
                tool_name = tool['name']
                server_id = tool['server_id']
                tool_args = extracted_arguments.get(tool_name, {})

                # Get tool schema to validate arguments
                tool_metadata = self.tool_manager.get_tool_metadata(server_id, tool_name)
                if tool_metadata and tool_metadata.get('schema'):
                    tool_args = self._validate_and_clean_args(
                        tool_args, tool_metadata['schema']
                    )

                tool_calls.append({
                    'tool_name': tool_name,
                    'server_id': server_id,
                    'arguments': tool_args,
                    'confidence': tool.get('match_score', 0)
                })

            return {
                'original_request': original_request,
                'tool_calls': tool_calls,
                'execution_plan': self._create_execution_plan(tool_calls),
                'fallback_strategy': 'ai_only' if not tool_calls else 'hybrid'
            }

        except Exception as e:
            logger.error(f"Error translating request to MCP: {str(e)}")
            return {
                'original_request': original_request,
                'tool_calls': [],
                'error': str(e),
                'fallback_strategy': 'ai_only'
            }

    def _validate_and_clean_args(self, args: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and clean arguments against tool schema"""
        clean_args = {}
        properties = schema.get('properties', {})
        required = schema.get('required', [])

        # Add required fields with defaults if missing
        for prop_name, prop_schema in properties.items():
            if prop_name in required and prop_name not in args:
                default_value = prop_schema.get('default')
                if default_value is not None:
                    clean_args[prop_name] = default_value

        # Add provided arguments that are in the schema
        for arg_name, arg_value in args.items():
            if arg_name in properties:
                # Type conversion/casting could be added here
                clean_args[arg_name] = arg_value

        return clean_args

    def _create_execution_plan(self, tool_calls: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create optimal execution plan for multiple tool calls"""
        if not tool_calls:
            return {'type': 'none'}

        if len(tool_calls) == 1:
            return {
                'type': 'single',
                'tool_call': tool_calls[0]
            }

        # For multiple tools, determine execution order
        # High confidence tools first
        sorted_calls = sorted(tool_calls, key=lambda x: x['confidence'], reverse=True)

        return {
            'type': 'multiple',
            'tool_calls': sorted_calls,
            'parallel_possible': self._can_run_parallel(sorted_calls),
            'estimated_duration': self._estimate_duration(sorted_calls)
        }

    def _can_run_parallel(self, tool_calls: List[Dict[str, Any]]) -> bool:
        """Determine if tool calls can run in parallel"""
        # Simple heuristic: tools with different categories can often run in parallel
        categories = [call.get('category', 'unknown') for call in tool_calls]
        return len(set(categories)) == len(tool_calls)

    def _estimate_duration(self, tool_calls: List[Dict[str, Any]]) -> int:
        """Estimate total execution duration in seconds"""
        # Base estimates by tool type
        duration_estimates = {
            'weather': 2,
            'search': 3,
            'calculation': 1,
            'data_access': 2,
            'default': 2
        }

        total_duration = 0
        for call in tool_calls:
            tool_name = call['tool_name']
            category = self._get_tool_category(tool_name)
            duration = duration_estimates.get(category, duration_estimates['default'])
            total_duration += duration

        return total_duration

    def _get_tool_category(self, tool_name: str) -> str:
        """Get category for a tool name"""
        # Simple mapping - in production, this would come from tool metadata
        if 'weather' in tool_name.lower():
            return 'weather'
        elif 'search' in tool_name.lower():
            return 'search'
        elif 'calculate' in tool_name.lower() or 'math' in tool_name.lower():
            return 'calculation'
        elif 'data' in tool_name.lower() or 'database' in tool_name.lower():
            return 'data_access'
        else:
            return 'default'

    def preserve_original_context(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Maintain original request context and metadata"""
        return {
            'original_text': request.get('text', ''),
            'original_format': request.get('format', 'unknown'),
            'original_headers': request.get('headers', {}),
            'original_metadata': request.get('metadata', {}),
            'timestamp': request.get('timestamp')
        }