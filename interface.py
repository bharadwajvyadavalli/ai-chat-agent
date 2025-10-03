from flask import Flask, render_template_string, request, jsonify
from agent import Agent
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import config

agent = Agent()

# Console Interface
def console():
    """Start console chat"""
    print("\n🤖 AI Chat Agent")
    print("Commands: 'email' to send last 5 messages, 'quit' to exit\n")
    
    while True:
        try:
            user_input = input("You: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ['quit', 'exit']:
                print("Goodbye!")
                break
            
            if user_input.lower() == 'email':
                send_email()
                continue
            
            result = agent.process(user_input)
            print(f"\nAgent: {result['response']}")
            if result['tools_used']:
                print(f"[Tools: {', '.join(result['tools_used'])}]")
            print()
        
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}\n")


# Email Service
def send_email(n=5):
    """Send last n exchanges via email"""
    if not config.GMAIL_EMAIL or not config.GMAIL_PASSWORD:
        print("Email not configured")
        return False
    
    messages = agent.storage.get_all_messages()
    
    # Group into exchanges
    exchanges = []
    for i in range(0, len(messages)-1, 2):
        if i+1 < len(messages) and messages[i]['role'] == 'user':
            exchanges.append((messages[i], messages[i+1]))
    
    exchanges = exchanges[-n:]
    
    html = f"<html><body><h2>Your Last {len(exchanges)} Conversations</h2>"
    for user_msg, agent_msg in exchanges:
        html += f"<p><strong>You:</strong> {user_msg['content']}</p>"
        html += f"<p><strong>Agent:</strong> {agent_msg['content']}</p>"
        if agent_msg.get('tools_used'):
            html += f"<p><em>Tools: {', '.join(agent_msg['tools_used'])}</em></p>"
        html += "<hr>"
    html += "</body></html>"
    
    try:
        message = MIMEMultipart()
        message['From'] = config.GMAIL_EMAIL
        message['To'] = config.GMAIL_EMAIL
        message['Subject'] = f"AI Agent - Last {len(exchanges)} Conversations"
        message.attach(MIMEText(html, 'html'))
        
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(config.GMAIL_EMAIL, config.GMAIL_PASSWORD)
            server.send_message(message)
        
        print("✓ Email sent!")
        return True
    except Exception as e:
        print(f"✗ Email error: {e}")
        return False


# Web Interface
app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>AI Chat Agent</title>
    <style>
        body { font-family: Arial; max-width: 800px; margin: 50px auto; padding: 20px; }
        .chat { height: 400px; overflow-y: auto; border: 1px solid #ccc; padding: 20px; margin-bottom: 20px; }
        .message { margin: 10px 0; }
        .user { text-align: right; }
        .agent { text-align: left; }
        .bubble { display: inline-block; padding: 10px 15px; border-radius: 10px; max-width: 70%; }
        .user .bubble { background: #007bff; color: white; }
        .agent .bubble { background: #f1f1f1; }
        .tools { font-size: 11px; color: #666; margin-top: 5px; }
        input { width: 80%; padding: 10px; }
        button { padding: 10px 20px; }
    </style>
</head>
<body>
    <h1>🤖 AI Chat Agent</h1>
    <div class="chat" id="chat">
        <div class="message agent">
            <div class="bubble">Hi! I can help with calculations and find information. What would you like to know?</div>
        </div>
    </div>
    <input type="text" id="input" placeholder="Type your message..." onkeypress="if(event.key=='Enter') send()">
    <button onclick="send()">Send</button>
    <button onclick="sendEmail()">📧 Email Last 5</button>
    
    <script>
        async function send() {
            const input = document.getElementById('input');
            const message = input.value.trim();
            if (!message) return;
            
            addMessage('user', message);
            input.value = '';
            
            const response = await fetch('/chat', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({message})
            });
            
            const data = await response.json();
            addMessage('agent', data.response, data.tools_used);
        }
        
        function addMessage(role, content, tools) {
            const chat = document.getElementById('chat');
            const div = document.createElement('div');
            div.className = 'message ' + role;
            
            let toolsHtml = '';
            if (tools && tools.length > 0) {
                toolsHtml = '<div class="tools">🔧 ' + tools.join(', ') + '</div>';
            }
            
            div.innerHTML = '<div class="bubble">' + content + toolsHtml + '</div>';
            chat.appendChild(div);
            chat.scrollTop = chat.scrollHeight;
        }
        
        async function sendEmail() {
            const response = await fetch('/email', {method: 'POST'});
            const data = await response.json();
            alert(data.message);
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    result = agent.process(data['message'])
    return jsonify(result)

@app.route('/email', methods=['POST'])
def email():
    success = send_email()
    return jsonify({'message': '✓ Email sent!' if success else '✗ Email failed'})

def web():
    """Start web interface"""
    print("\n🌐 Starting web interface on http://localhost:8000")
    app.run(host='0.0.0.0', port=8000, debug=False)
