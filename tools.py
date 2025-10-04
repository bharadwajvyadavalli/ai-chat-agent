#!/usr/bin/env python3
"""
Tools for AI Chat Agent

This module provides Calculator and Wikipedia tools for the AI chat agent.
These tools are used by the MCP server to provide functionality to external clients.
"""

import re
import wikipedia
from typing import Optional


class Calculator:
    """Calculator tool for mathematical operations"""
    
    def __init__(self):
        self.name = "calculator"
        self.description = "Perform mathematical calculations and solve equations"
    
    def execute(self, expression: str) -> str:
        """
        Execute a mathematical expression safely
        
        Args:
            expression: Mathematical expression to evaluate
            
        Returns:
            Result of the calculation or error message
        """
        try:
            # Clean and validate the expression
            expression = expression.strip()
            
            # Remove any non-mathematical characters for security
            allowed_chars = set('0123456789+-*/().,eE ')
            if not all(c in allowed_chars for c in expression):
                return "Error: Invalid characters in expression. Only numbers, operators (+, -, *, /), parentheses, and spaces are allowed."
            
            # Replace common mathematical terms
            expression = expression.replace('×', '*').replace('÷', '/')
            expression = expression.replace('**', '**')  # Keep power operator
            
            # Evaluate the expression
            result = eval(expression)
            
            # Format the result
            if isinstance(result, float):
                if result.is_integer():
                    result = int(result)
                else:
                    result = round(result, 6)
            
            return str(result)
            
        except ZeroDivisionError:
            return "Error: Division by zero"
        except SyntaxError:
            return "Error: Invalid mathematical expression"
        except Exception as e:
            return f"Error: {str(e)}"


class Wikipedia:
    """Wikipedia tool for information retrieval"""
    
    def __init__(self):
        self.name = "wikipedia"
        self.description = "Search Wikipedia for information about topics, people, places"
        
        # Configure wikipedia library
        wikipedia.set_lang("en")
        wikipedia.set_rate_limiting(True)
    
    def execute(self, query: str) -> str:
        """
        Search Wikipedia for information
        
        Args:
            query: Search query for Wikipedia
            
        Returns:
            Wikipedia information or error message
        """
        try:
            # Clean the query
            query = query.strip()
            if not query:
                return "Error: Empty search query"
            
            # Try to get a summary first
            try:
                # Search for pages
                search_results = wikipedia.search(query, results=3)
                
                if not search_results:
                    return f"No Wikipedia articles found for '{query}'"
                
                # Get the first result
                page_title = search_results[0]
                
                # Get the page
                page = wikipedia.page(page_title)
                
                # Return summary (first 500 characters)
                summary = page.summary
                if len(summary) > 500:
                    summary = summary[:500] + "..."
                
                return f"Wikipedia: {page_title}\n\n{summary}"
                
            except wikipedia.exceptions.DisambiguationError as e:
                # Handle disambiguation pages
                options = e.options[:5]  # Limit to first 5 options
                return f"Multiple articles found for '{query}'. Please be more specific:\n\n" + "\n".join(f"- {option}" for option in options)
            
            except wikipedia.exceptions.PageError:
                return f"No Wikipedia article found for '{query}'"
            
        except Exception as e:
            return f"Error searching Wikipedia: {str(e)}"


# For backward compatibility and testing
if __name__ == "__main__":
    # Test the tools
    calc = Calculator()
    wiki = Wikipedia()
    
    print("Testing Calculator:")
    print(f"2 + 2 = {calc.execute('2 + 2')}")
    print(f"10 * 5 = {calc.execute('10 * 5')}")
    print(f"100 / 4 = {calc.execute('100 / 4')}")
    
    print("\nTesting Wikipedia:")
    print(f"Python: {wiki.execute('Python programming')}")
    print(f"Einstein: {wiki.execute('Albert Einstein')}")
