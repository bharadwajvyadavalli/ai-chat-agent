# 🤖 AI Chat Agent

Smart AI agent that automatically uses Calculator and Wikipedia tools based on your questions.

## Features

- **Smart Tool Routing**: Auto-detects when to use Calculator, Wikipedia, both, or neither
- **Persistent Storage**: All conversations saved locally
- **Email Summaries**: Send conversation history via email
- **Dual Interface**: Console and Web UI

## Quick Start

### 1. Install
```bash
pip install -r requirements.txt
```

### 2. Configure
Create `.env` file:
```
OPENAI_API_KEY=your_key_here
GMAIL_EMAIL=your_email@gmail.com          # Optional
GMAIL_PASSWORD=your_gmail_app_password    # Optional
```

### 3. Run
```bash
# Console mode
python main.py

# Web mode
python main.py web
```

## Examples

```
You: What is 156 * 23?
Agent: 156 multiplied by 23 equals 3,588.
[Tools: calculator]

You: Who was Albert Einstein?
Agent: Albert Einstein was a German-born theoretical physicist...
[Tools: wikipedia]

You: Calculate the square of the year Einstein was born
Agent: Einstein was born in 1879, and 1879² = 3,531,641.
[Tools: wikipedia, calculator]
```

## Project Structure

```
ai-chat-agent/
├── main.py          # Entry point
├── agent.py         # Agent + LLM integration
├── tools.py         # Calculator + Wikipedia
├── storage.py       # Message persistence
├── interface.py     # Console + Web UI
├── config.py        # Configuration
└── requirements.txt
```

## Commands (Console Mode)

- Type your message to chat
- `email` - Send last 5 messages to email
- `quit` - Exit

## Web Interface

Run `python main.py web` and open http://localhost:5000

## License

MIT
