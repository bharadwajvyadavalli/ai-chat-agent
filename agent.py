import json
from openai import OpenAI
import config
from tools import Calculator, Wikipedia
from storage import Storage

client = OpenAI(api_key=config.OPENAI_API_KEY)

SYSTEM_PROMPT = """You are an AI assistant with access to Calculator and Wikipedia tools.

Analyze each message and decide which tools to use:
- Calculator: for math, calculations, equations
- Wikipedia: for facts, information, people, places
- Both: when you need both calculation and information
- None: for greetings and general chat

Return JSON: {"tools": ["calculator"|"wikipedia"|"none"], "reasoning": "why"}"""


class Agent:
    def __init__(self):
        self.storage = Storage()
        self.calculator = Calculator()
        self.wikipedia = Wikipedia()
    
    def process(self, user_message):
        """Process user message and return response"""
        # Get conversation history
        history = self.storage.get_last_messages(6)
        
        # Decide which tools to use
        tool_decision = self._decide_tools(user_message, history)
        tools_to_use = tool_decision.get('tools', ['none'])
        
        # Execute tools
        tool_results = {}
        for tool in tools_to_use:
            if tool == 'calculator':
                tool_results['calculator'] = self.calculator.execute(user_message)
            elif tool == 'wikipedia':
                tool_results['wikipedia'] = self.wikipedia.execute(user_message)
        
        # Generate response
        response = self._generate_response(user_message, tool_results, history)
        
        # Save to storage
        self.storage.save_message('user', user_message)
        self.storage.save_message('assistant', response, list(tool_results.keys()), tool_results)
        
        return {
            'response': response,
            'tools_used': list(tool_results.keys())
        }
    
    def _decide_tools(self, message, history):
        """Ask LLM which tools to use"""
        messages = [{'role': 'system', 'content': SYSTEM_PROMPT}]
        
        # Add recent history
        for msg in history[-4:]:
            messages.append({'role': msg['role'], 'content': msg['content']})
        
        messages.append({'role': 'user', 'content': f"Decide tools for: {message}"})
        
        try:
            response = client.chat.completions.create(
                model=config.MODEL,
                messages=messages,
                temperature=0.3,
                max_tokens=200
            )
            
            content = response.choices[0].message.content
            # Extract JSON
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0]
            elif '```' in content:
                content = content.split('```')[1].split('```')[0]
            
            return json.loads(content.strip())
        except:
            return {'tools': ['none'], 'reasoning': 'Error deciding tools'}
    
    def _generate_response(self, user_message, tool_results, history):
        """Generate final response using tool results"""
        messages = [
            {'role': 'system', 'content': 'You are a helpful AI assistant. Use the tool results to answer naturally.'}
        ]
        
        # Add history
        for msg in history[-6:]:
            messages.append({'role': msg['role'], 'content': msg['content']})
        
        # Build prompt with tool results
        prompt = f"User: {user_message}\n\n"
        if tool_results:
            prompt += "Tool Results:\n"
            for tool, result in tool_results.items():
                prompt += f"- {tool}: {result}\n"
        
        messages.append({'role': 'user', 'content': prompt})
        
        try:
            response = client.chat.completions.create(
                model=config.MODEL,
                messages=messages,
                temperature=config.TEMPERATURE
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error generating response: {e}"
