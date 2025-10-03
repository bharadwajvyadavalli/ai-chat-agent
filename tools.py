import re
import math
import wikipediaapi

class Calculator:
    def execute(self, query):
        """Perform mathematical calculations"""
        expression = self._extract_expression(query)
        try:
            # Safe eval with math functions
            safe_dict = {'sqrt': math.sqrt, 'pi': math.pi, 'e': math.e, '__builtins__': {}}
            result = eval(expression, safe_dict)
            return str(round(result, 10) if isinstance(result, float) else result)
        except Exception as e:
            return f"Error: {e}"
    
    def _extract_expression(self, query):
        query = query.lower()
        query = re.sub(r'\b(what is|calculate|equals?)\b', '', query)
        query = query.replace('times', '*').replace('plus', '+').replace('minus', '-')
        query = query.replace('divided by', '/').replace('^', '**').replace('x', '*')
        return query.strip()


class Wikipedia:
    def __init__(self):
        self.wiki = wikipediaapi.Wikipedia(language='en', user_agent='AIAgent/1.0')
    
    def execute(self, query):
        """Search Wikipedia for information"""
        search_term = self._extract_search_term(query)
        page = self.wiki.page(search_term)
        
        if not page.exists():
            return f"No Wikipedia page found for '{search_term}'"
        
        # Get first 3 sentences
        summary = page.summary
        sentences = summary.split('. ')[:3]
        return '. '.join(sentences) + '.'
    
    def _extract_search_term(self, query):
        query = query.lower()
        query = re.sub(r'^(who is|who was|what is|tell me about)\s+', '', query)
        query = query.replace('?', '').strip()
        return ' '.join(word.capitalize() for word in query.split())
