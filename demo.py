import os
import json
import sys
import autogen
from autogen import UserProxyAgent, GroupChat, GroupChatManager, ConversableAgent
from autogen.io.websockets import IOWebsockets
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import uvicorn
from contextlib import asynccontextmanager

quiet_mode = "--quiet" in sys.argv or "-q" in sys.argv

def console_log(message):
    if not quiet_mode:
        print(message)

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise ValueError("Missing OpenAI API Key. Set OPENAI_API_KEY environment variable.")

PORT = 9999

discussion_active = False

try:
    config_path = "CONFIG_LIST.json"
    config_list = autogen.config_list_from_json(config_path)

    for config in config_list:
        if config.get("api_key") is None:
            config["api_key"] = api_key

    llm_config = {"config_list": config_list}

    console_log("Loaded LLM configuration successfully")
except Exception as e:
    console_log(f"Error loading LLM configuration: {e}")
    llm_config = {
        "config_list": [
            {
                "api_type": "openai",
                "model": "gpt-4o",
                "api_key": api_key
            }
        ]
    }

def on_connect(iostream: IOWebsockets) -> None:
    """Handle new WebSocket connection and start classroom discussion."""
    global discussion_active

    console_log(f"[WebSocket] New client connected: {iostream}")

    try:
        initial_msg = iostream.input()
        console_log(f"Initial message from client: {initial_msg}")

        try:
            if isinstance(initial_msg, str):
                parsed_initial = json.loads(initial_msg)
                if isinstance(parsed_initial, dict) and parsed_initial.get("type") == "command":
                    if parsed_initial.get("content") == "restart_discussion":
                        console_log("Restart command received - treating as new discussion")
                        discussion_active = False
                        initial_msg = "start_discussion"
        except json.JSONDecodeError:
            pass
    except Exception as e:
        console_log(f"Error receiving initial message: {e}")
        return

    if discussion_active:
        console_log("A discussion is already active")
        try:
            iostream.send(json.dumps({
                "type": "system_message",
                "content": "A discussion is already in progress."
            }))
        except Exception as e:
            console_log(f"Error sending busy message: {e}")
        return

    discussion_active = True

    try:
        teacher = ConversableAgent(
            name="Teacher",
            system_message="""You are a teacher facilitating a classroom discussion on various topics.
            Ask thought-provoking questions and guide the discussion in an educational manner.
            Keep your responses concise (2-3 paragraphs maximum) and engaging, suitable for a classroom setting.
            Try to relate topics to real-world examples that students would find interesting.

            Respond to student questions even if they deviate from the main topic. Be adaptable and willing
            to change direction if students show interest in a different but related area.
            """,
            description="The teacher who facilitates the classroom discussion",
            llm_config=llm_config
        )

        user_proxy = UserProxyAgent(
            name="You",
            human_input_mode="ALWAYS",
            system_message="You are participating in a classroom discussion. Share your thoughts and ask questions.",
            description="The human user participating in the discussion",
            code_execution_config=False,
            is_termination_msg=lambda x: isinstance(x, str) and x.lower().strip() == "exit" or
                (isinstance(x, dict) and x.get("content", "").lower().strip() == "exit"),
        )

        def custom_input(prompt=None):
            """Handle user input via WebSocket, ensuring structured JSON messages."""
            console_log(f"User's turn to respond: {prompt}")

            if prompt:
                try:
                    console_log("Waiting for user input via WebSocket...")
                except Exception as e:
                    console_log(f"Error in custom_input: {e}")

            while True:
                try:
                    raw_message = iostream.input()

                    if isinstance(raw_message, str):
                        raw_message = raw_message.strip()

                    try:
                        if isinstance(raw_message, str):
                            parsed_message = json.loads(raw_message)
                        else:
                            parsed_message = raw_message

                        if parsed_message.get("type") == "ping":
                            console_log("Ping received, keeping connection alive")
                            continue

                        if parsed_message.get("type") == "user_message":
                            return parsed_message["content"]
                        elif parsed_message.get("type") == "terminate":
                            console_log("Exit command received. Terminating discussion.")
                            return "exit"
                        elif parsed_message.get("type") == "command" and parsed_message.get("content") == "restart_discussion":
                            console_log("Restart command received during discussion. Terminating current session.")
                            return "exit"
                        else:
                            console_log(f"Unknown message type received: {parsed_message}")
                            return raw_message

                    except json.JSONDecodeError:
                        console_log(f"Could not parse as JSON, returning raw: {raw_message}")
                        return raw_message

                except Exception as e:
                    console_log(f"Error receiving user input: {e}")
                    return "exit"

        user_proxy.get_human_input = custom_input

        group_chat = GroupChat(
            agents=[teacher, user_proxy],
            messages=[],
            max_round=30,
            speaker_selection_method="round_robin",
            allow_repeat_speaker=True
        )

        chat_manager = GroupChatManager(
            groupchat=group_chat,
            name="chat_manager",
            llm_config=llm_config,
        )

        if initial_msg.lower() == "start_discussion":
            start_msg = """Start a classroom discussion about an interesting scientific topic that would engage students. Begin by introducing the topic and asking an open-ended question. Keep the discussion engaging and educational."""
        else:
            start_msg = initial_msg

        user_proxy.initiate_chat(
            chat_manager,
            message=start_msg
        )

    except Exception as e:
        console_log(f"Error in classroom discussion: {e}")
        try:
            iostream.send(json.dumps({
                "type": "error",
                "message": str(e)
            }))
        except Exception as ws_error:
            console_log(f"WebSocket send error in on_connect: {ws_error}")

    finally:
        discussion_active = False
        console_log("Classroom discussion has concluded.")

html = """

<!DOCTYPE html>
<html>
    <head>
        <title>Multiversity Office Hours</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
        <style>
            :root {
                --color-teacher: #15803d;
                --color-teacher-bg: #dcfce7;
                --color-student: #9333ea;
                --color-student-bg: #f3e8ff;
                --color-you: #1e40af;
                --color-you-bg: #dbeafe;
                --color-system: #78350f;
                --color-system-bg: #fef3c7;
            }

            * { box-sizing: border-box; margin: 0; padding: 0; }

            body {
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
                line-height: 1.5;
                color: #1f2937;
                background-color: #f3f4f6;
                padding: 1rem;
                height: 100vh;
                display: flex;
                flex-direction: column;
            }

            .container {
                max-width: 800px;
                margin: 0 auto;
                flex-grow: 1;
                display: flex;
                flex-direction: column;
                height: 100%;
            }

            header {
                text-align: center;
                margin-bottom: 1.5rem;
            }

            header h1 {
                font-size: 1.75rem;
                color: #1f2937;
                margin-bottom: 0.25rem;
            }

            header p {
                color: #6b7280;
                font-size: 0.875rem;
            }

            .chat-container {
                background-color: white;
                border-radius: 0.5rem;
                box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
                display: flex;
                flex-direction: column;
                flex-grow: 1;
                overflow: hidden;
            }

            .connection-status {
                padding: 0.75rem 1rem;
                font-size: 0.8125rem;
                color: #6b7280;
                display: flex;
                align-items: center;
                justify-content: space-between;
                border-bottom: 1px solid #e5e7eb;
            }

            .status-indicator {
                display: flex;
                align-items: center;
            }

            .status-dot {
                width: 8px;
                height: 8px;
                border-radius: 50%;
                margin-right: 0.5rem;
            }

            .status-dot.connected { background-color: #10b981; }
            .status-dot.connecting { background-color: #f59e0b; }
            .status-dot.disconnected { background-color: #ef4444; }

            .actions {
                display: flex;
                gap: 8px;
            }

            .action-button {
                background: none;
                border: 1px solid #e5e7eb;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 0.75rem;
                cursor: pointer;
                transition: all 0.2s;
            }

            .action-button:hover {
                background-color: #f9fafb;
            }

            .messages {
                flex: 1;
                padding: 1rem;
                overflow-y: auto;
                display: flex;
                flex-direction: column;
                gap: 0.75rem;
            }

            .message {
                padding: 0.75rem;
                border-radius: 0.5rem;
                max-width: 85%;
                position: relative;
                animation: fadeIn 0.3s ease;
            }

            @keyframes fadeIn {
                from { opacity: 0; transform: translateY(10px); }
                to { opacity: 1; transform: translateY(0); }
            }

            .message .sender {
                font-weight: 600;
                font-size: 0.75rem;
                margin-bottom: 0.5rem;
                display: flex;
                justify-content: space-between;
                align-items: baseline;
                width: 100%;
            }

            .message .sender .name,

            .message .content {
                font-size: 0.875rem;
                white-space: pre-wrap;
                line-height: 1.5;
                word-break: break-word;
            }

            .message .time {
                display: inline-block;
                line-height: 1.2;
                vertical-align: baseline;
                color: #6b7280;
                margin-left: 0.75rem;
            }

            .message.teacher {
                background-color: var(--color-teacher-bg);
                align-self: flex-start;
                color: #000;
            }

            .message.you {
                background-color: var(--color-you-bg);
                align-self: flex-end;
                color: #000;
                min-width: 80px;
            }

            .message.system {
                background-color: var(--color-system-bg);
                align-self: center;
                text-align: center;
                font-style: italic;
                max-width: 90%;
                font-size: 0.8125rem;
            }

            .typing-indicator {
                align-self: flex-start;
                background-color: #f3f4f6;
                border-radius: 10px;
                padding: 8px 12px;
                margin-bottom: 8px;
                display: none;
                font-size: 0.875rem;
            }

            .typing-indicator.active {
                display: flex;
                align-items: center;
            }

            .dot {
                width: 6px;
                height: 6px;
                background-color: #6b7280;
                border-radius: 50%;
                margin: 0 1px;
                animation: typing 1.4s infinite ease-in-out;
            }

            .dot:nth-child(1) { animation-delay: 0s; }
            .dot:nth-child(2) { animation-delay: 0.2s; }
            .dot:nth-child(3) { animation-delay: 0.4s; }

            @keyframes typing {
                0%, 60%, 100% { transform: translateY(0); }
                30% { transform: translateY(-4px); }
            }

            .input-area {
                padding: 1rem;
                display: flex;
                border-top: 1px solid #e5e7eb;
            }

            .input-area textarea {
                flex: 1;
                padding: 0.75rem 1rem;
                border: 1px solid #d1d5db;
                border-radius: 0.375rem;
                font-size: 0.875rem;
                resize: none;
                height: 60px;
                font-family: inherit;
            }

            .input-area textarea:focus {
                outline: none;
                border-color: #3b82f6;
                box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.3);
            }

            .send-button {
                background-color: #3b82f6;
                color: white;
                border: none;
                border-radius: 0.375rem;
                padding: 0.75rem 1.5rem;
                font-weight: 500;
                margin-left: 0.75rem;
                cursor: pointer;
                transition: background-color 0.2s;
            }

            .send-button:hover {
                background-color: #2563eb;
            }

            .send-button:disabled {
                background-color: #9ca3af;
                cursor: not-allowed;
            }

            @media (max-width: 640px) {
                .input-area {
                    flex-direction: column;
                }

                .send-button {
                    margin-left: 0;
                    margin-top: 0.5rem;
                }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <h1>Multiversity Office Hours</h1>
                <p>Learn by discussing various topics with AI agents...</p>
            </header>

            <div class="chat-container">
                <div class="connection-status">
                    <div class="status-indicator">
                        <div id="status-dot" class="status-dot connecting"></div>
                        <span id="status-text">Connecting...</span>
                    </div>
                    <div class="actions">
                        <button id="clear-btn" class="action-button">Clear Chat</button>
                        <button id="restart-btn" class="action-button">Restart</button>
                    </div>
                </div>

                <div id="messages" class="messages">
                    <!-- Messages will appear here -->
                </div>

                <div id="typing-indicator" class="typing-indicator">
                    <span id="typing-name"></span>&nbsp;is typing
                    <div class="dots">
                        <div class="dot"></div>
                        <div class="dot"></div>
                        <div class="dot"></div>
                    </div>
                </div>

                <div class="input-area">
                    <textarea id="message-input" placeholder="Type your message here..."></textarea>
                    <button id="send-button" class="send-button">Send</button>
                </div>
            </div>
        </div>

        <script>
            const messagesContainer = document.getElementById('messages');
            const messageInput = document.getElementById('message-input');
            const sendButton = document.getElementById('send-button');
            const statusDot = document.getElementById('status-dot');
            const statusText = document.getElementById('status-text');
            const clearBtn = document.getElementById('clear-btn');
            const restartBtn = document.getElementById('restart-btn');
            const typingIndicator = document.getElementById('typing-indicator');
            const typingName = document.getElementById('typing-name');

            function safeJsonParse(str) {
                try {
                    return JSON.parse(str);
                } catch (e) {
                    console.error('Error parsing JSON:', e);
                    return { type: 'system_message', content: str };
                }
            }

            let ws = null;

            let connecting = false;
            let reconnecting = false;

            function connectWebSocket() {
                if ((ws && ws.readyState === WebSocket.OPEN) ||
                    (ws && ws.readyState === WebSocket.CONNECTING && !reconnecting)) {
                    console.log("WebSocket is already connected or connecting.");
                    return;
                }

                connecting = true;
                updateConnectionStatus('connecting', 'Connecting...');

                ws = new WebSocket(`ws://localhost:8080`);

                let retryAttempts = 0;
                const maxRetries = 5;

                function retrySendMessage() {
                    if (retryAttempts >= maxRetries) {
                        console.error("Max WebSocket retry attempts reached. Stopping retries.");
                        addSystemMessage("Failed to establish connection. Please refresh the page.");
                        return;
                    }

                    setTimeout(() => {
                        try {
                            if (ws && ws.readyState === WebSocket.OPEN) {
                                console.log("Sending start_discussion command");
                                ws.send('start_discussion');
                            } else {
                                console.warn("WebSocket not ready. Retrying...");
                                retrySendMessage();
                            }
                        } catch (e) {
                            console.error("WebSocket send error in retrySendMessage:", e);
                        }
                    }, 500);
                }

                let discussionStarted = false;

                ws.onopen = function() {
                    console.log("WebSocket connection opened");
                    updateConnectionStatus('connected', 'Connected');
                    connecting = false;

                    console.log("Sending start_discussion command");
                    ws.send(JSON.stringify({"type": "command", "content": "start_discussion"}));

                    startHeartbeat();
                };

                ws.onmessage = function(event) {
                    console.log("Raw WebSocket message received:", event.data);

                    try {
                        const message = JSON.parse(event.data);

                        console.log("Parsed message:", message);

                        if (message.type === "text" && message.content) {
                            const parsedContent = safeJsonParse(message.content.content);
                            addAgentMessage(message.content.sender_name, parsedContent.content || message.content.content);
                        }
                        else if (message.type === "user_message") {
                            addAgentMessage("You", message.content);
                        }
                        else if (message.type === "terminate") {
                            addSystemMessage("The discussion has ended.");
                        }
                        else {
                            console.log("Ignoring system message:", message);
                        }
                    } catch (e) {
                        console.error("Error parsing message:", e);
                        addSystemMessage(`Unexpected message from server: ${event.data}`);
                    }
                };

                function safeJsonParse(str) {
                    try {
                        return JSON.parse(str);
                    } catch (e) {
                        return { content: str };
                    }
                }

                ws.onclose = function() {
                    updateConnectionStatus('disconnected', 'Disconnected');
                    console.log("WebSocket connection closed");
                    connecting = false;
                };

                ws.onerror = function(error) {
                    console.error("WebSocket error:", error);
                    updateConnectionStatus('disconnected', 'Error occurred');
                };
            }

            function determineMessageType(content) {
                if (!content) return;

                if (content.startsWith("Teacher:")) {
                    const actualContent = content.substring(8).trim();
                    addAgentMessage("Teacher", actualContent);
                } else if (content.startsWith("You:")) {
                    const actualContent = content.substring(4).trim();
                    addAgentMessage("You", actualContent);
                } else {
                    addSystemMessage(content);
                }
            }

            function handleMessage(message) {
                console.log('Processing message:', message);

                if (message.type === 'agent_message') {
                    console.log(`Processing agent message from ${message.agent}: "${message.content?.substring(0, 50)}..."`);
                    hideTypingIndicator();

                    try {
                        addAgentMessage(message.agent, message.content);
                        console.log(`Successfully added ${message.agent} message to UI`);
                    } catch (error) {
                        console.error("Error adding agent message to UI:", error);
                        addSystemMessage(`Error displaying message from ${message.agent}: ${error.message}`);
                    }
                } else if (message.type === 'system_message') {
                    console.log('Processing system message');
                    addSystemMessage(message.content);
                } else if (message.type === 'agent_typing') {
                    console.log(`Showing typing indicator for ${message.agent}`);
                    showTypingIndicator(message.agent);
                } else if (message.type === 'message') {
                    determineMessageType(message.content);
                } else {
                    console.log('Unknown message type:', message);
                    addSystemMessage('Received: ' + JSON.stringify(message));
                }
            }

            function showTypingIndicator(agent) {
                typingName.textContent = agent;
                typingIndicator.classList.add('active');
                typing = true;
            }

            function hideTypingIndicator() {
                typingIndicator.classList.remove('active');
                typing = false;
            }

            function addAgentMessage(agent, content) {
                const messageEl = document.createElement('div');
                messageEl.className = `message ${agent.toLowerCase()}`;

                const now = new Date();
                const time = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

                messageEl.innerHTML = `
                    <div class="sender">
                        <span class="name">${agent}</span>
                        <span class="time">${time}</span>
                    </div>
                    <div class="content">${content}</div>
                `;

                messagesContainer.appendChild(messageEl);
                scrollToBottom();
            }

            function addSystemMessage(content) {
                const messageEl = document.createElement('div');
                messageEl.className = 'message system';
                messageEl.innerHTML = `<div class="content">${content}</div>`;

                messagesContainer.appendChild(messageEl);
                scrollToBottom();
            }

            function sendMessage() {
                const message = messageInput.value.trim();
                if (!message) return;

                const formattedMessage = JSON.stringify({
                    type: "user_message",
                    content: message
                });

                if (ws && ws.readyState === WebSocket.OPEN) {
                    try {
                        console.log("Sending message:", formattedMessage);
                        ws.send(formattedMessage);

                        messageInput.value = '';
                    } catch (error) {
                        console.error("WebSocket send error:", error);
                        addSystemMessage("Error sending message");
                    }
                } else {
                    console.error("WebSocket is not connected.");
                    addSystemMessage("Not connected to server");
                }

                messageInput.focus();
            }

            function startHeartbeat() {
                if (window.heartbeatInterval) {
                    clearInterval(window.heartbeatInterval);
                }

                window.heartbeatInterval = setInterval(function() {
                    if (ws && ws.readyState === WebSocket.OPEN) {
                        try {
                            ws.send(JSON.stringify({
                                type: "ping",
                                content: "keepalive"
                            }));
                            console.log("Ping sent to keep connection alive");
                        } catch (e) {
                            console.error("Error sending ping:", e);
                        }
                    } else {
                        console.log("WebSocket not open, skipping heartbeat");
                    }
                }, 30000);
            }

            function clearChat() {
                if (confirm('Clear all messages?')) {
                    messagesContainer.innerHTML = '';
                    addSystemMessage('Chat history cleared');
                }
            }

            function restartDiscussion() {
                if (confirm('Restart the classroom discussion?')) {
                    messagesContainer.innerHTML = '';
                    addSystemMessage('Restarting classroom discussion...');

                    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
                        try {
                            console.log("Sending restart command");
                            ws.send(JSON.stringify({
                                "type": "command",
                                "content": "restart_discussion"
                            }));

                            console.log("Closing current WebSocket connection");
                            ws.close();
                        } catch (e) {
                            console.error("Error during restart:", e);
                            addSystemMessage("Error restarting discussion");
                        }
                    }

                    setTimeout(function() {
                        console.log("Attempting to reconnect...");
                        connectWebSocket();
                    }, 2000);
                }
            }

            function updateConnectionStatus(status, text) {
                statusDot.className = `status-dot ${status}`;
                statusText.textContent = text;
            }

            function scrollToBottom() {
                messagesContainer.scrollTop = messagesContainer.scrollHeight;
            }

            sendButton.addEventListener('click', sendMessage);

            messageInput.addEventListener('keypress', function(e) {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    sendMessage();
                }
            });

            clearBtn.addEventListener('click', clearChat);
            restartBtn.addEventListener('click', restartDiscussion);

            window.addEventListener('load', function() {
                connectWebSocket();
                addSystemMessage('Welcome to the classroom discussion');
            });
        </script>
    </body>
</html>
"""

@asynccontextmanager
async def lifespan(app):
    """Application lifespan context manager."""
    try:
        with IOWebsockets.run_server_in_thread(on_connect=on_connect, port=8080) as uri:
            console_log(f"WebSocket server started at {uri}")
            yield
    except Exception as e:
        console_log(f"Error running WebSocket server: {e}")
    finally:
        console_log("WebSocket server stopped")

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def get():
    """Serve the HTML interface."""
    return HTMLResponse(html)

@app.get("/status")
async def status():
    """Return server status."""
    return {
        "status": "running",
        "discussion_active": discussion_active
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)