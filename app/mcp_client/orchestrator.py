"""
MCP Response Orchestration

This module handles the merging of AI responses with MCP tool results
to create coherent, intelligent responses for clients.
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Optional, Any, Union

logger = logging.getLogger(__name__)

class MCPResponseOrchestrator:
    """
    Orchestrates the combination of AI responses with MCP tool results
    """

    def __init__(self, mcp_client):
        self.mcp_client = mcp_client
        self.response_templates = MCPResponseTemplates()
        self.streaming_orchestrator = MCPStreamingOrchestrator(self)

    async def orchestrate_response(self, original_request: str, mcp_analysis: Dict[str, Any],
                                 ai_client: Optional[Any] = None) -> Dict[str, Any]:
        """
        Main orchestration method that coordinates AI and MCP responses

        Args:
            original_request: Original user request
            mcp_analysis: Result from intent detection and tool analysis
            ai_client: AI client for fallback/primary responses

        Returns:
            Orchestrated response
        """
        try:
            start_time = time.time()
            tool_calls = mcp_analysis.get('tool_calls', [])
            execution_plan = mcp_analysis.get('execution_plan', {})

            logger.info(f"Orchestrating response with {len(tool_calls)} tool calls")

            # Execute MCP tools if needed
            tool_results = []
            if tool_calls:
                tool_results = await self._execute_tools(tool_calls, execution_plan)

            # Generate AI response if needed
            ai_response = None
            if ai_client and self._should_include_ai_response(tool_results, mcp_analysis):
                ai_response = await self._generate_ai_response(
                    original_request, tool_results, ai_client
                )

            # Merge responses
            final_response = await self.merge_ai_and_tools(
                ai_response, tool_results, original_request, mcp_analysis
            )

            # Calculate response time
            response_time = int((time.time() - start_time) * 1000)

            result = {
                'response': final_response,
                'tool_results': tool_results,
                'ai_response': ai_response,
                'metadata': {
                    'response_time_ms': response_time,
                    'tools_used': len(tool_results),
                    'ai_enhanced': ai_response is not None,
                    'orchestration_strategy': self._determine_strategy(tool_results, ai_response)
                }
            }

            logger.info(f"Response orchestrated in {response_time}ms")
            return result

        except Exception as e:
            logger.error(f"Error in response orchestration: {str(e)}")
            return {
                'response': f"I apologize, but I encountered an error while processing your request: {str(e)}",
                'error': str(e),
                'metadata': {
                    'orchestration_failed': True,
                    'fallback_used': True
                }
            }

    async def _execute_tools(self, tool_calls: List[Dict[str, Any]],
                            execution_plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Execute the specified tool calls"""
        try:
            if not tool_calls:
                return []

            plan_type = execution_plan.get('type', 'single')

            if plan_type == 'single':
                # Execute single tool
                tool_call = tool_calls[0]
                result = await self._execute_single_tool(tool_call)
                return [result] if result else []

            elif plan_type == 'multiple':
                parallel_possible = execution_plan.get('parallel_possible', False)

                if parallel_possible and len(tool_calls) > 1:
                    # Execute tools in parallel
                    return await self._execute_tools_parallel(tool_calls)
                else:
                    # Execute tools sequentially
                    return await self._execute_tools_sequential(tool_calls)

            return []

        except Exception as e:
            logger.error(f"Error executing tools: {str(e)}")
            return []

    async def _execute_single_tool(self, tool_call: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Execute a single tool call"""
        try:
            tool_name = tool_call['tool_name']
            server_id = tool_call['server_id']
            arguments = tool_call['arguments']

            logger.info(f"Executing tool: {tool_name} on server: {server_id}")

            # Use the MCP client to call the tool
            result = await self.mcp_client.call_tool(tool_name, arguments)

            return {
                'tool_name': tool_name,
                'server_id': server_id,
                'arguments': arguments,
                'result': result,
                'success': result.get('success', False),
                'confidence': tool_call.get('confidence', 0)
            }

        except Exception as e:
            logger.error(f"Error executing single tool: {str(e)}")
            return {
                'tool_name': tool_call.get('tool_name', 'unknown'),
                'server_id': tool_call.get('server_id', 'unknown'),
                'arguments': tool_call.get('arguments', {}),
                'result': None,
                'success': False,
                'error': str(e),
                'confidence': 0
            }

    async def _execute_tools_parallel(self, tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Execute multiple tools in parallel"""
        try:
            logger.info(f"Executing {len(tool_calls)} tools in parallel")

            tasks = [self._execute_single_tool(tool_call) for tool_call in tool_calls]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Filter out exceptions and None results
            valid_results = []
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Parallel tool execution error: {str(result)}")
                elif result is not None:
                    valid_results.append(result)

            return valid_results

        except Exception as e:
            logger.error(f"Error in parallel tool execution: {str(e)}")
            return []

    async def _execute_tools_sequential(self, tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Execute multiple tools sequentially"""
        try:
            logger.info(f"Executing {len(tool_calls)} tools sequentially")

            results = []
            for tool_call in tool_calls:
                result = await self._execute_single_tool(tool_call)
                if result:
                    results.append(result)

                # Small delay between sequential calls
                await asyncio.sleep(0.1)

            return results

        except Exception as e:
            logger.error(f"Error in sequential tool execution: {str(e)}")
            return []

    def _should_include_ai_response(self, tool_results: List[Dict[str, Any]],
                                  mcp_analysis: Dict[str, Any]) -> bool:
        """Determine if AI response should be included"""
        if not tool_results:
            return True  # No tools, use AI only

        # Check if any tools failed
        failed_tools = [r for r in tool_results if not r.get('success', False)]
        if failed_tools:
            return True  # Some tools failed, use AI as fallback

        # Check if tools provide complete answer
        successful_tools = [r for r in tool_results if r.get('success', False)]
        if len(successful_tools) == 1:
            # Single successful tool might be enough, but check confidence
            tool_result = successful_tools[0]
            if tool_result.get('confidence', 0) < 3:
                return True  # Low confidence, enhance with AI

        # Check overall confidence
        avg_confidence = sum(r.get('confidence', 0) for r in successful_tools) / len(successful_tools)
        if avg_confidence < 2.5:
            return True  # Low overall confidence, enhance with AI

        return False

    async def _generate_ai_response(self, original_request: str, tool_results: List[Dict[str, Any]],
                                  ai_client: Any) -> str:
        """Generate AI response enhanced with tool results"""
        try:
            # Create context from tool results
            tool_context = self._create_tool_context(tool_results)

            # Create enhanced prompt
            enhanced_prompt = self._create_enhanced_prompt(original_request, tool_context)

            # This would use the actual AI client - for now, return a mock response
            # In production, this would call: await ai_client.generate(enhanced_prompt)
            mock_response = f"Based on the information I found, here's what I can tell you about your request: '{original_request}'."

            if tool_context:
                mock_response += f" Additional context: {tool_context}"

            return mock_response

        except Exception as e:
            logger.error(f"Error generating AI response: {str(e)}")
            return f"I apologize, but I had trouble processing your request. Here's what I found from the tools: {tool_context}"

    def _create_tool_context(self, tool_results: List[Dict[str, Any]]) -> str:
        """Create context string from tool results"""
        context_parts = []

        for result in tool_results:
            if not result.get('success', False):
                continue

            tool_name = result['tool_name']
            tool_result = result.get('result', {})

            if isinstance(tool_result, dict):
                if tool_result.get('success'):
                    context_parts.append(f"{tool_name}: {tool_result.get('result', 'No result')}")
                else:
                    context_parts.append(f"{tool_name}: Error - {tool_result.get('error', 'Unknown error')}")
            else:
                context_parts.append(f"{tool_name}: {tool_result}")

        return "; ".join(context_parts)

    def _create_enhanced_prompt(self, original_request: str, tool_context: str) -> str:
        """Create enhanced prompt for AI with tool context"""
        if tool_context:
            return f"""Original request: {original_request}

Additional information from tools: {tool_context}

Please provide a comprehensive response that incorporates both the original request and the additional information above."""
        else:
            return original_request

    async def merge_ai_and_tools(self, ai_response: Optional[str], tool_results: List[Dict[str, Any]],
                               original_request: str, mcp_analysis: Dict[str, Any]) -> str:
        """Merge AI response with tool results"""
        try:
            successful_tools = [r for r in tool_results if r.get('success', False)]
            failed_tools = [r for r in tool_results if not r.get('success', False)]

            # Handle different scenarios
            if not successful_tools and not ai_response:
                return "I apologize, but I wasn't able to process your request. The tools I tried to use didn't work properly."

            if not successful_tools and ai_response:
                return ai_response

            if successful_tools and not ai_response:
                return self._format_tool_only_response(successful_tools, original_request)

            # Both tools and AI response available
            return self._format_hybrid_response(ai_response, successful_tools, failed_tools, original_request)

        except Exception as e:
            logger.error(f"Error merging responses: {str(e)}")
            return f"I encountered an error while combining the results: {str(e)}"

    def _format_tool_only_response(self, tool_results: List[Dict[str, Any]], original_request: str) -> str:
        """Format response when only tools are used"""
        if len(tool_results) == 1:
            result = tool_results[0]
            tool_result_data = result.get('result', {})

            if isinstance(tool_result_data, dict):
                if tool_result_data.get('success'):
                    return str(tool_result_data.get('result', 'No result available'))
                else:
                    return f"I apologize, but the tool encountered an error: {tool_result_data.get('error', 'Unknown error')}"
            else:
                return str(tool_result_data)
        else:
            # Multiple tools
            response_parts = []
            for result in tool_results:
                tool_name = result['tool_name']
                tool_result_data = result.get('result', {})

                if isinstance(tool_result_data, dict) and tool_result_data.get('success'):
                    response_parts.append(f"{tool_name}: {tool_result_data.get('result', 'No result')}")
                else:
                    response_parts.append(f"{tool_name}: {tool_result_data}")

            return "Here's what I found:\n\n" + "\n\n".join(response_parts)

    def _format_hybrid_response(self, ai_response: str, successful_tools: List[Dict[str, Any]],
                              failed_tools: List[Dict[str, Any]], original_request: str) -> str:
        """Format response combining AI and tools"""
        # Use response template to format hybrid response
        template_type = self._select_response_template(successful_tools, failed_tools)
        template = self.response_templates.get_template(template_type)

        # Prepare tool results string
        tool_results_str = ""
        if successful_tools:
            tool_results_str = "\n\nAdditional information:\n"
            for result in successful_tools:
                tool_name = result['tool_name']
                tool_result_data = result.get('result', {})
                if isinstance(tool_result_data, dict) and tool_result_data.get('success'):
                    tool_results_str += f"• {tool_result_data.get('result', 'No result')}\n"

        # Add failed tools info if any
        if failed_tools:
            tool_results_str += "\n\nNote: Some tools I tried to use didn't work properly."

        return template.format(
            ai_response=ai_response,
            tool_results=tool_results_str.strip(),
            original_request=original_request
        )

    def _select_response_template(self, successful_tools: List[Dict[str, Any]],
                                failed_tools: List[Dict[str, Any]]) -> str:
        """Select appropriate response template"""
        if failed_tools and successful_tools:
            return 'partial_success'
        elif len(successful_tools) == 1:
            return 'single_tool'
        else:
            return 'multiple_tools'

    def _determine_strategy(self, tool_results: List[Dict[str, Any]], ai_response: Optional[str]) -> str:
        """Determine the orchestration strategy used"""
        if not tool_results and ai_response:
            return 'ai_only'
        elif tool_results and not ai_response:
            return 'tools_only'
        elif tool_results and ai_response:
            return 'hybrid'
        else:
            return 'error'

    async def orchestrate_streaming_response(self, original_request: str, mcp_analysis: Dict[str, Any],
                                          ai_client: Optional[Any] = None):
        """
        Handle streaming responses with MCP tool integration

        Yields response chunks as they become available
        """
        async for chunk in self.streaming_orchestrator.orchestrate_streaming_response(
            original_request, mcp_analysis, ai_client
        ):
            yield chunk

class MCPResponseTemplates:
    """Response templates for different scenarios"""

    def __init__(self):
        self.templates = {
            'single_tool': """{ai_response}

{tool_results}""",

            'multiple_tools': """{ai_response}

{tool_results}""",

            'partial_success': """{ai_response}

{tool_results}

Some additional information I tried to gather wasn't available, but I hope this helps with your request!""",

            'data_enrichment': """Based on the data I found: {tool_results}

{ai_response}""",

            'tool_execution': """I've completed the task you requested. Here are the results:

{tool_results}

{ai_response}""",

            'error_fallback': """I encountered some issues, but here's what I can tell you: {ai_response}

{tool_results}""",

            'hybrid_analysis': """{ai_response}

Here's the supporting information I found:

{tool_results}"""
        }

    def get_template(self, template_type: str) -> str:
        """Get template by type, fallback to default"""
        return self.templates.get(template_type, self.templates['hybrid_analysis'])

    def select_template(self, request_type: str, tool_success_count: int, total_tools: int) -> str:
        """Choose appropriate response template based on context"""
        if tool_success_count == 0:
            return 'error_fallback'
        elif tool_success_count == total_tools:
            if tool_success_count == 1:
                return 'single_tool'
            else:
                return 'multiple_tools'
        else:
            return 'partial_success'

    def populate_template(self, template: str, ai_response: str, tool_results: str,
                         original_request: str = "") -> str:
        """Fill template with actual content"""
        return template.format(
            ai_response=ai_response,
            tool_results=tool_results,
            original_request=original_request
        )

class MCPStreamingOrchestrator:
    """Handles streaming responses with MCP tool integration"""

    def __init__(self, orchestrator: MCPResponseOrchestrator):
        self.orchestrator = orchestrator

    async def orchestrate_streaming_response(self, original_request: str, mcp_analysis: Dict[str, Any],
                                          ai_client: Optional[Any] = None):
        """Orchestrate streaming response with tool integration"""
        try:
            tool_calls = mcp_analysis.get('tool_calls', [])

            # Start with acknowledgment
            yield {
                'type': 'start',
                'content': "I'm working on your request..."
            }

            # Execute tools if needed
            if tool_calls:
                yield {
                    'type': 'tools_start',
                    'content': f"Let me gather some information for you using {len(tool_calls)} tool{'s' if len(tool_calls) > 1 else ''}..."
                }

                tool_results = await self.orchestrator._execute_tools(
                    tool_calls, mcp_analysis.get('execution_plan', {})
                )

                yield {
                    'type': 'tools_complete',
                    'content': f"I've gathered the information. Let me formulate a response for you...",
                    'tool_results': tool_results
                }
            else:
                tool_results = []

            # Generate and stream AI response
            if ai_client:
                yield {
                    'type': 'ai_start',
                    'content': "Now let me provide you with a comprehensive response..."
                }

                # Mock streaming - in production, this would stream from AI client
                ai_response_chunks = [
                    "Based on your request and the information I gathered, ",
                    "I can provide you with the following insights. ",
                    "The tools I used helped me find relevant data that ",
                    "directly addresses what you're looking for."
                ]

                for chunk in ai_response_chunks:
                    yield {
                        'type': 'ai_chunk',
                        'content': chunk
                    }
                    await asyncio.sleep(0.2)  # Simulate streaming delay

                ai_response = "".join(ai_response_chunks)
            else:
                ai_response = None

            # Final merged response
            final_response = await self.orchestrator.merge_ai_and_tools(
                ai_response, tool_results, original_request, mcp_analysis
            )

            yield {
                'type': 'complete',
                'content': final_response,
                'metadata': {
                    'tools_used': len(tool_results),
                    'ai_enhanced': ai_response is not None
                }
            }

        except Exception as e:
            logger.error(f"Error in streaming orchestration: {str(e)}")
            yield {
                'type': 'error',
                'content': f"I apologize, but encountered an error: {str(e)}",
                'error': str(e)
            }