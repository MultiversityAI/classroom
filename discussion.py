import sys
import os
import json
import re
import autogen
from autogen import UserProxyAgent, GroupChat, GroupChatManager, ConversableAgent
from autogen.io.websockets import IOWebsockets
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from contextlib import asynccontextmanager
import logging

logging.basicConfig(level=logging.INFO)

def console_log(message):
    logging.info(message)

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    console_log("CRITICAL: OpenAI API Key is missing. Cannot start application.")
    sys.exit(1)

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

try:
    with open("students.json", "r") as f:
        student_data = json.load(f)
    console_log("Loaded student data successfully")
except Exception as e:
    console_log(f"Error loading student data: {e}. Using default student data.")
    student_data = [
        {
            "name": "Alvin",
            "system_message": """You are Alvin, a curious and creative student who often makes unexpected connections between topics.
            You have a tendency to jump ahead and suggest new ideas before others are ready.
            You sometimes make minor misconceptions but are always eager to learn.""",
            "description": "A curious student who makes creative connections but sometimes has misconceptions"
        },
        {
            "name": "Bianca",
            "system_message": """You are Bianca, a confident student who often speaks with authority.
            You sometimes present common misconceptions with confidence, which can be useful for classroom discussion.
            You are receptive to corrections but initially defend your position.""",
            "description": "A confident student who sometimes presents misconceptions with authority"
        },
        {
            "name": "Charlie",
            "system_message": """You are Charlie, a thoughtful student who asks metacognitive questions.
            You help guide group thinking and often ask clarifying questions that help everyone understand.
            You're interested in how people think about problems, not just the answers.""",
            "description": "A thoughtful student focused on metacognition and group understanding"
        }
    ]

def find_next_speaker(last_message_content, agent_names):
    if not last_message_content:
        return None

    last_message_content = last_message_content.strip()
    console_log(f"🔍 Analyzing message to find next speaker: {last_message_content[:100]}...")

    sentences = re.split(r'[.!?]\s+', last_message_content)
    sentences = [s.strip() for s in sentences if s.strip()]

    valid_agents = {"You", "Teacher"} | set(agent_names)

    if sentences:
        last_two_sentences = sentences[-2:] if len(sentences) >= 2 else sentences
        for sentence in last_two_sentences:
            for name in valid_agents:
                pattern = r'\b{}\b'.format(re.escape(name))
                if re.search(pattern, sentence):
                    console_log(f"🎯 Found direct call-out to: {name}")
                    return name

    agent_regex = r"({})".format("|".join(re.escape(name) for name in valid_agents))

    patterns = [
        rf"(?:^|\W){agent_regex}(?:,|\.|\?|!|\s).*?\?$",
        rf"(?:^|\W){agent_regex}(?:,|\.|\?|!|\s).*thoughts",
        rf"(?:^|\W){agent_regex}(?:,|\.|\?|!|\s).*think",
        rf"Let's hear from\s+{agent_regex}",
        rf"{agent_regex},\s+would you",
        rf"What (?:do|about|are) (?:you|your).*,\s+{agent_regex}",
        rf"{agent_regex},\s+what",
        rf"What do you think,?\s+{agent_regex}",
        rf"Do you (?:have|think).*,?\s+{agent_regex}",
        rf"How about you,?\s+{agent_regex}",
        rf"{agent_regex},\s+(?:do|can|could) you",
        rf"(?:Do|Can|Could|Would) {agent_regex}",
        rf"I'd like to hear from\s+{agent_regex}",
        rf"{agent_regex}\s+(?:should|could|would) (?:you|your)",
        rf"hear (?:your|) thoughts,?\s+{agent_regex}",
        rf"ask\s+{agent_regex}",
    ]

    for pattern in patterns:
        matches = re.findall(pattern, last_message_content, re.IGNORECASE)
        if matches:
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]
                if match in valid_agents:
                    console_log(f"🎯 Found direct call-out to: {match}")
                    return match

    if "Teacher" in valid_agents:
        console_log("⚠️ No valid student was explicitly called. Defaulting to 'Teacher'.")
        return "Teacher"

    console_log("⚠️ No valid participant found. Defaulting to 'You'.")
    return "You"

def custom_speaker_selection(last_speaker, group_chat, iostream=None):
    agent_names = [agent.name for agent in group_chat.agents]

    last_message = group_chat.messages[-1] if group_chat.messages else None
    if not last_message:
        return next(agent for agent in group_chat.agents if agent.name == "Teacher")

    last_speaker_name = last_message.get("sender", "")
    last_content = last_message.get("content", "").strip()

    if last_speaker_name == "Teacher" and "See you next time!" in last_content:
        if iostream:
            try:
                iostream.send(json.dumps({
                    "type": "system_message",
                    "content": "The discussion has concluded. See you next time!"
                }))
            except Exception as e:
                console_log(f"🚨 Error sending system message: {e}")
        return None

    if re.search(r"\bsee you next time\b", last_content, re.IGNORECASE):
        if iostream:
            try:
                iostream.send(json.dumps({
                    "type": "system_message",
                    "content": "The discussion is concluding. Thank you all!"
                }))
            except Exception as e:
                console_log(f"🚨 Error sending system message: {e}")
        return None

    next_speaker = find_next_speaker(last_content, agent_names)
    if next_speaker is None or next_speaker not in agent_names:
        next_speaker = "Teacher"

    if next_speaker and next_speaker in agent_names:
        next_agent = next(agent for agent in group_chat.agents if agent.name == next_speaker)

        if iostream:
            try:
                iostream.send(json.dumps({
                    "type": "system_message",
                    "content": f"It's {next_speaker}'s turn to speak."
                }))
            except Exception as e:
                console_log(f"🚨 Error sending next speaker notification: {e}")

        return next_agent

    return next(agent for agent in group_chat.agents if agent.name == "Teacher")

discussion_active = False

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
                    if parsed_initial.get("content") == "restart":
                        console_log("Restart command received - treating as new discussion")
                        discussion_active = False
                        initial_msg = "start"
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
            system_message=f"""You are a knowledgeable teacher leading a classroom discussion.

            📜 RULES FOR CALLING ON PARTICIPANTS:
            - You MUST always call on a specific participant at the end of each message.
            - Choose ONLY from this list of students: {", ".join([s['name'] for s in student_data])}, or "You" (the human user).
            - NEVER invent names. If unsure, call on "You" (the human user).

            If you call on an invalid name, the conversation will not progress. Follow these rules strictly.

            🚀 YOUR RESPONSIBILITIES:
            - Ask thought-provoking questions.
            - Call on specific students or the human user by name to participate.
            - Guide the discussion and ensure everyone gets a turn.
            - Address misconceptions and encourage deeper thinking.
            - Summarize key points at appropriate moments.
            - **End discussions gracefully and efficiently without unnecessary repetition.**

            🔥 ALWAYS end your message with a direct call-out:
            - "[name], what do you think?"
            - "[name], do you have an example?"
            - "You, what's your take on this?"

            ❌ Do NOT ask 'anyone' in general.
            ❌ Do NOT call on non-existent students.
            ❌ Do NOT end without calling on someone.

            If you do not follow these instructions, the discussion will stall. Stick to the given names.

            📜 RULES FOR ENDING THE DISCUSSION:
            Always invite "You" (the human user) to share final thoughts before concluding.

            Example: "You, before we wrap up, do you have any final takeaways from today's discussion?"
            If "You" does not respond or has nothing to add, provide a single final summary and conclude the session.

            DO NOT call on students once the discussion is ending.

            If students have already shared their thoughts, there is no need to ask them again.
            Wrap up with a clear and warm closing message.

            Example: "Thank you all for the great discussion! Keep thinking critically, and I look forward to our next session!"
            Optionally, pose a reflective question for students to think about before the next session.

            🛑 FINAL MESSAGE STRUCTURE
            Once "You" has spoken (or opted out), DO NOT ask more questions. Instead, wrap up with:

            A thank you to participants.
            A brief summary of key discussion points.
            An optional reflection question for students to consider.
            A clear conclusion without starting a new discussion.

            Example Final Message:
            "Thank you all for today's discussion! We explored X, Y, and Z. Keep thinking critically about these ideas.
            As a final thought, how might you apply these concepts in real life? See you next time!"

            🚨 DO NOT start a new discussion after concluding. Your closing message MUST include "See you next time!"
            """,
            description="A teacher facilitating the classroom discussion",
            llm_config=llm_config
        )

        student_agents = []

        for student in student_data:
            student["system_message"] += f"""
            **📜 IMPORTANT GUIDELINES FOR PARTICIPATION**

            1. **Always end your messages by calling on a specific classmate, the teacher, or "You" (the human user).**
            - **You may only call on:** {", ".join([s['name'] for s in student_data if s['name'] != student['name']])}, "Teacher," or "You."  
            - **DO NOT call on yourself.** If unsure, call on "Teacher."

            👀 Examples:
            - *"What do you think about this, [classmate's name]?"*
            - *"[classmate's name], have you considered this perspective?"*
            - *"Teacher, what's your perspective on this?"*
            - *"You, have you experienced something similar?"*

            2. **Make your call-out direct and specific.**
            - Phrase it as a question that invites a response.

            3. **DO NOT end with vague questions.**
            - ❌ *"What does everyone think?"*
            - ❌ *"Any thoughts?"*

            4. **Always speak in the first person.**
            - You are **{student["name"]}**, so **always refer to yourself as "I"**, not in the third person.

            5. **DO NOT answer questions directed at others.**
            - If another participant is called on, **wait for them to respond.**
            - 🛑 DO NOT send messages like *"WAITING FOR XYZ TO RESPOND."*
            - **Simply stay silent until it is your turn.**
            """

            student_agent = ConversableAgent(
                name=student["name"],
                system_message=student["system_message"],
                description=student["description"],
                llm_config=llm_config
            )
            student_agents.append(student_agent)

        user_proxy = UserProxyAgent(
            name="You",
            human_input_mode="ALWAYS",
            system_message="You are participating in a classroom discussion. Share your thoughts when called upon.",
            description="The human user participating in the discussion",
            code_execution_config=False,
            is_termination_msg=lambda x: isinstance(x, str) and x.lower().strip() == "exit" or
                (isinstance(x, dict) and x.get("content", "").lower().strip() == "exit"),
        )

        all_participants = [teacher] + student_agents + [user_proxy]

        all_agent_names = [agent.name for agent in all_participants]
        console_log(f"All agents: {all_agent_names}")

        try:
            agent_list_msg = {
                "type": "agent_list",
                "content": all_agent_names
            }
            iostream.send(json.dumps(agent_list_msg))
            console_log("✅ Sent agent list to client")
        except Exception as e:
            console_log(f"🚨 Error sending agent list: {e}")

        def custom_input(prompt=None):
            """Handle user input via WebSocket, ensuring structured JSON messages."""
            console_log(f"📝 User's turn to respond: {prompt}")

            while True:
                try:
                    raw_message = iostream.input()

                    if isinstance(raw_message, str):
                        raw_message = raw_message.strip()

                    try:
                        parsed_message = json.loads(raw_message) if isinstance(raw_message, str) else raw_message

                        if isinstance(parsed_message, dict):
                            message_type = parsed_message.get("type")

                            if message_type == "ping" or parsed_message.get("content") == "keepalive":
                                console_log("📡 Ping or keepalive received, ignoring...")
                                continue

                            if message_type == "user_message":
                                return parsed_message["content"]

                            elif message_type == "terminate":
                                console_log("🛑 Exit command received. Terminating discussion.")
                                return "exit"

                            elif message_type == "command" and parsed_message.get("content") == "restart":
                                console_log("🔄 Restart command received. Terminating session.")
                                return "exit"

                            else:
                                console_log(f"⚠️ Unknown message type received: {parsed_message}")
                                return json.dumps(parsed_message)

                        else:
                            console_log(f"⚠️ Could not parse as JSON, returning raw: {raw_message}")
                            return json.dumps({"type": "user_message", "content": raw_message})

                    except json.JSONDecodeError:
                        console_log(f"⚠️ Could not parse as JSON, returning raw: {raw_message}")
                        return json.dumps({"type": "user_message", "content": raw_message})

                except Exception as e:
                    console_log(f"🚨 Error receiving user input: {e}")
                    return "exit"

        user_proxy.get_human_input = custom_input

        def send_message(agent_name, content):
            try:
                console_log(f"📤 Sending message from {agent_name}: {content[:100]}...")

                if isinstance(content, dict):
                    content_str = json.dumps(content)
                elif not isinstance(content, str):
                    content_str = str(content)
                else:
                    content_str = content

                message_data = {
                    "type": "agent_message",
                    "agent": agent_name,
                    "content": content_str
                }

                json_str = json.dumps(message_data)
                iostream.send(json_str)
                console_log(f"✅ Sent message from {agent_name}: {content_str[:50]}...")

            except Exception as e:
                console_log(f"🚨 Error sending message: {e}")
                console_log(f"🚨 ERROR OCCURRED! Object Type: {type(content)} Content: {repr(content)[:100]}")

        for agent in all_participants:
            def create_message_handler(agent_name):
                def message_handler(recipient, messages=None, sender=None, config=None):
                    try:
                        if messages and len(messages) > 0:
                            last_message = messages[-1]
                            if last_message.get("role") == "assistant":
                                content = last_message.get("content", "")

                                if isinstance(content, dict):
                                    content = json.dumps(content)
                                elif not isinstance(content, str):
                                    content = str(content)

                                if content:
                                    send_message(agent_name, content)
                                    console_log(f"✅ Handled message from {agent_name}")
                    except Exception as e:
                        console_log(f"🚨 Error in message handler for {agent_name}: {e}")
                    return False, None

                return message_handler

            handler = create_message_handler(agent.name)
            agent.register_reply(ConversableAgent, handler)

        group_chat = GroupChat(
            agents=all_participants,
            messages=[],
            max_round=30,
            speaker_selection_method=lambda last_speaker, chat: custom_speaker_selection(last_speaker, chat, iostream),
            allow_repeat_speaker=False
        )

        chat_manager = GroupChatManager(
            groupchat=group_chat,
            name="chat_manager",
            llm_config=llm_config,
        )

        if isinstance(initial_msg, str) and initial_msg.lower() == "start":
            start_msg = """Start a classroom discussion about an interesting scientific concept that students might find challenging. 
            Begin by introducing the topic, explaining why it's important, and asking an open-ended question that encourages critical thinking.
            Keep the discussion engaging and educational, drawing connections to real-world applications when possible.
            After your introduction, call on a specific student by name to respond."""
        else:
            start_msg = initial_msg

        try:
            user_proxy.initiate_chat(chat_manager, message={"type": "start_message", "content": start_msg})
            console_log("✅ user_proxy.initiate_chat() started successfully.")
        except Exception as e:
            console_log(f"🚨 ERROR in initiate_chat: {e}")

    except Exception as e:
        console_log(f"Error in classroom discussion: {e}")
        try:
            error_data = {
                "type": "error",
                "message": str(e)
            }
            error_json = json.dumps(error_data)
            iostream.send(error_json)
            console_log(f"DEBUG: Sent error message: {error_json}")
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
                --color-student-alvin: #9333ea;
                --color-student-alvin-bg: #f3e8ff;
                --color-student-bianca: #ca8a04;
                --color-student-bianca-bg: #fef9c3;
                --color-student-charlie: #0369a1;
                --color-student-charlie-bg: #e0f2fe;
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
                padding-bottom: 1.5rem;
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
                border-radius: 0.888rem;
                box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
                display: flex;
                flex-direction: column;
                flex-grow: 1;
                overflow: hidden;
                padding-bottom: 12px;
                margin-bottom: 12px;
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
                border-radius: 3px;
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

            .message.alvin {
                background-color: var(--color-student-alvin-bg);
                align-self: flex-start;
                color: #000;
            }

            .message.bianca {
                background-color: var(--color-student-bianca-bg);
                align-self: flex-start;
                color: #000;
            }

            .message.charlie {
                background-color: var(--color-student-charlie-bg);
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
                font-size: 0.888rem;
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
                flex-direction: column;
                border-top: 1px solid #e5e7eb;
                background-color: #ffffff;
                border-radius: 0 0 0.5rem 0.5rem;
                transition: all 0.3s ease;
            }

            .input-container {
                display: flex;
                position: relative;
                height: 93px;
                padding: 0.75rem 80px 1rem 1rem;
                margin-bottom: 8px;
            }

            .textarea-wrapper {
                flex: 1;
                position: relative;
                display: flex;
                align-items: center;
            }

            .input-actions-area {
                position: absolute;
                right: 0;
                top: 15px;
                bottom: 0;
                width: 70px;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                z-index: 10;
                margin-left: 12px;
            }

            .input-area textarea {
                flex: 1;
                width: 100%;
                padding: 0.75rem 80px 0.75rem 1rem;
                border: 1px solid #d1d5db;
                border-radius: .888rem;
                font-size: 0.95rem;
                resize: none;
                height: 93px;
                font-family: inherit;
                overflow-y: auto;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
                line-height: 1.5;
                box-sizing: border-box;
                -webkit-appearance: none;
                -webkit-tap-highlight-color: rgba(124, 157, 124, 0.25);
                appearance: none;
                margin-bottom: 19px;
            }

            .input-actions {
                position: absolute;
                right: 19px;
                top: 60%;
                transform: translateY(-50%);
                display: flex;
                flex-direction: column;
                align-items: center;
                gap: 5px;
                z-index: 10;
            }

            .action-icon {
                background: none;
                border: none;
                color: #6b7280;
                padding: 8px;
                border-radius: 50%;
                cursor: pointer;
                transition: all 0.2s;
                display: flex;
                align-items: center;
                justify-content: center;
            }

            .action-icon:hover {
                background-color: #f3f4f6;
                color: #3b82f6;
            }

            .send-button {
                background-color: #3E673E;
                color: white;
                border: none;
                border-radius: 50%;
                width: 40px;
                height: 40px;
                cursor: pointer;
                transition: all 0.2s;
                display: flex;
                align-items: center;
                justify-content: center;
            }

            .send-button:disabled {
                background-color: #9ca3af;
                transform: none;
                opacity: 0.7;
            }

            .send-button:hover:not(:disabled) {
                background-color: #7c9d7c;
                transform: scale(1.05);
            }

            .input-status {
                display: flex;
                justify-content: flex-end;
                align-items: center;
                margin-top: 0.5rem;
                padding: 0 0.5rem;
            }

            .character-count {
                background-color: rgba(255, 255, 255, 0.9);
                border-radius: 8px;
                padding: 5px 0 5px 0;
            }

            .current-turn-indicator {
                background-color: #f0f9ff;
                border: 2px solid #3b82f6;
                border-radius: 8px;
                padding: 6px 12px;
                margin: 8px 0;
                text-align: center;
                font-size: 0.875rem;
                font-weight: 500;
                color: #1e40af;
                animation: pulse 2s infinite;
            }

            @keyframes pulse {
                0% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.4); }
                70% { box-shadow: 0 0 0 6px rgba(59, 130, 246, 0); }
                100% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0); }
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

            .message .sender .name {
                padding: 2px 8px;
                border-radius: 4px;
                color: white;
            }

            .message.teacher .sender .name {
                background-color: var(--color-teacher);
            }

            .message.alvin .sender .name {
                background-color: var(--color-student-alvin);
            }

            .message.bianca .sender .name {
                background-color: var(--color-student-bianca);
            }

            .message.charlie .sender .name {
                background-color: var(--color-student-charlie);
            }

            .message.you .sender .name {
                background-color: var(--color-you);
            }

            .input-area textarea:focus {
                outline: none;
                border-color: #7c9d7c;
                box-shadow: 0 0 0 3px rgba(124, 157, 124, 0.25);
                -webkit-appearance: none;
                appearance: none;
            }

            .input-area textarea:focus-visible {
                outline-color: #7c9d7c;
            }

            .input-area textarea:active {
                border-color: #7c9d7c;
            }

            .input-area textarea:not(.expanded) {
                padding-top: 23px;
                padding-bottom: 19px;
                padding-right: 2rem;
                padding-left: 2rem;
            }

            .input-area.your-turn .turn-badge {
                display: block;
                animation: pulse 2s infinite;
            }

            .input-area.your-turn textarea {
                border-color: #3b82f6;
                background-color: #ffffff;
            }

            @media (max-width: 640px) {
                .input-area {
                    padding: 0.75rem;
                    margin-bottom: 10px;
                }

                .input-area textarea {
                    padding-right: 70px;
                    font-size: 16px;
                    padding: 0.75rem 4.5rem 0.75rem 0.75rem;
                }

                .send-button {
                    width: 36px;
                    height: 36px;
                }

                .input-actions {
                    width: 36px;
                    right: 12px;
                    gap: 5px;
                }

                .input-actions::before {
                    width: 60px;
                }

                body {
                    padding-bottom: 1rem;
                }

                .chat-container {
                    margin-bottom: 8px;
                    padding-bottom: 7px;
                }
            }

            @media not all and (min-resolution:.001dpcm) {
                @supports (-webkit-appearance:none) {
                    .input-area textarea:focus {
                        border-color: #7c9d7c !important;
                        outline-color: #7c9d7c !important;
                    }
                }
            }

            @media (max-width: 480px) {
                .input-area {
                    margin-bottom: 5px;
                    position: relative;
                }

                body {
                    padding-bottom: 0.5rem;
                }

                .chat-container {
                    min-height: 300px;
                }
            }

            @media screen and (-webkit-min-device-pixel-ratio: 0) {
                .input-area textarea {
                    font-size: max(16px, 0.95rem);
                }
            }

            .character-count.warning {
                color: #f59e0b;
                font-weight: bold;
            }

            .character-count.limit {
                color: #ef4444;
                font-weight: bold;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <h1>Multiversity Office Hours</h1>
                <p>Learn through discussions with AI agents...</p>
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
                </div>

                <div id="typing-indicator" class="typing-indicator">
                    <span id="typing-name"></span>&nbsp;is typing
                    <div class="dots">
                        <div class="dot"></div>
                        <div class="dot"></div>
                        <div class="dot"></div>
                    </div>
                </div>

                <div class="input-area" id="input-area">
                    <div class="input-container">
                        <textarea id="message-input" placeholder="Type your message here..."></textarea>
                        <div class="input-actions">
                            <button id="send-button" class="send-button" title="Send message">
                                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                    <line x1="22" y1="2" x2="11" y2="13"></line>
                                    <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
                                </svg>
                            </button>
                            <div class="character-count" id="character-count">0/250</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <script>
            const characterCount = document.getElementById('character-count');
            const inputArea = document.getElementById('input-area');
            const messagesContainer = document.getElementById('messages');
            const messageInput = document.getElementById('message-input');
            const sendButton = document.getElementById('send-button');
            const statusDot = document.getElementById('status-dot');
            const statusText = document.getElementById('status-text');
            const clearBtn = document.getElementById('clear-btn');
            const restartBtn = document.getElementById('restart-btn');
            const typingIndicator = document.getElementById('typing-indicator');
            const typingName = document.getElementById('typing-name');

            const MAX_CHARS = 250;
            messageInput.maxLength = MAX_CHARS;

            function safeJsonParse(str) {
                try {
                    return JSON.parse(str);
                } catch (e) {
                    console.error('Error parsing JSON:', e);
                    return { content: str };
                }
            }

            function findCalledAgent(messageContent) {
                if (!messageContent) return null;

                let agentNames = ["Teacher", "You"];

                function updateAgentNames(agents) {
                if (Array.isArray(agents)) {
                    agents.forEach(name => {
                    if (!agentNames.includes(name)) {
                        agentNames.push(name);
                    }
                    });
                    console.log("Updated agent names:", agentNames);
                }

                }
                const questionPatterns = [
                    /([A-Za-z]+),\s+(?:could|can|would)\s+you/i,
                    /What\s+(?:do|about)\s+you\s+think,\s+([A-Za-z]+)/i,
                    /([A-Za-z]+),\s+(?:what|how|do)/i,
                    /let's\s+hear\s+from\s+([A-Za-z]+)/i
                ];

                for (const pattern of questionPatterns) {
                    const match = messageContent.match(pattern);
                    if (match && match[1]) {
                        const potentialName = match[1].trim();
                        if (agentNames.includes(potentialName)) {
                            console.log(`Found direct question to: ${potentialName}`);
                            return potentialName;
                        }
                    }
                }

                const sentences = messageContent.split(/[.!?]\s+/);
                const lastSentences = sentences.slice(-2);

                for (const sentence of lastSentences) {
                    for (const name of agentNames) {
                        if (sentence.includes(`${name},`) || 
                            sentence.includes(`${name}?`) || 
                            sentence.match(new RegExp(`\\b${name}\\b.*\\?$`))) {
                            console.log(`Found agent in sentence: ${name}`);
                            return name;
                        }
                    }
                }

                return null;
            }

            document.addEventListener('DOMContentLoaded', function() {
                const messageInput = document.getElementById('message-input');
                const sendButton = document.getElementById('send-button');
                const characterCount = document.getElementById('character-count');
                const MAX_CHARS = 250;

                messageInput.maxLength = MAX_CHARS;
                sendButton.disabled = true;

                function updateCharacterCount() {
                    const currentLength = messageInput.value.length;
                    const isEmpty = messageInput.value.trim() === '';

                    characterCount.textContent = `${currentLength}/${MAX_CHARS}`;

                    characterCount.classList.remove('warning', 'limit');

                    if (currentLength > MAX_CHARS) {
                        characterCount.classList.add('limit');
                        characterCount.style.color = '#ef4444';
                        characterCount.style.fontWeight = 'bold';
                    } else if (currentLength > MAX_CHARS * 0.9) {
                        characterCount.classList.add('warning');
                        characterCount.style.color = '#f59e0b';
                        characterCount.style.fontWeight = 'bold';
                    } else {
                        characterCount.style.color = '#6b7280';
                        characterCount.style.fontWeight = 'normal';
                    }

                    sendButton.disabled = isEmpty || (currentLength > MAX_CHARS);
                }

                messageInput.addEventListener('input', updateCharacterCount);

                if ('visualViewport' in window) {
                    window.visualViewport.addEventListener('resize', function() {
                        document.body.style.height = window.visualViewport.height + 'px';
                    });
                }

                messageInput.addEventListener('focus', function() {
                    setTimeout(function() {
                        messageInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    }, 300);
                });

                updateCharacterCount();
            });

            sendButton.disabled = true;

            messageInput.addEventListener('input', function() {
                sendButton.disabled = this.value.trim() === '';
            });

            sendButton.disabled = true;

            function updateUserTurnVisual(isUserTurn) {
                if (isUserTurn) {
                    inputArea.classList.add('your-turn');
                    messageInput.placeholder = "Your turn! Type your response...";
                    messageInput.focus();

                    messageInput.style.animation = 'none';
                    setTimeout(() => {
                        messageInput.style.animation = 'pulse 2s';
                    }, 10);
                } else {
                    inputArea.classList.remove('your-turn');
                    messageInput.placeholder = "Type your message here...";
                }
            }

            function showTypingIndicator(agent) {
                if (!agent) return;
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

                if (agent !== "You" && agent !== "System") {
                    const calledPerson = findCalledAgent(content);
                    if (calledPerson === "You") {
                        userTurn = true;
                        updateUserTurnVisual(true);
                        messageInput.focus();

                        const flashInput = () => {
                            messageInput.style.borderColor = '#10b981';
                            messageInput.style.boxShadow = '0 0 0 4px rgba(16, 185, 129, 0.5)';

                            setTimeout(() => {
                                messageInput.style.borderColor = '#d1d5db';
                                messageInput.style.boxShadow = 'none';

                                setTimeout(() => {
                                    messageInput.style.borderColor = '#10b981';
                                    messageInput.style.boxShadow = '0 0 0 4px rgba(16, 185, 129, 0.5)';

                                    setTimeout(() => {
                                        updateUserTurnVisual(true);
                                    }, 300);
                                }, 300);
                            }, 300);
                        };

                        flashInput();
                    }
                }
            }

            function addSystemMessage(content) {
                const messageEl = document.createElement('div');
                messageEl.className = 'message system';
                messageEl.innerHTML = `<div class="content">${content}</div>`;

                messagesContainer.appendChild(messageEl);
                scrollToBottom();
            }

            function handleMessage(message) {
                console.log('Processing message:', message);

                if (message.type === 'agent_message') {
                    console.log(`Processing agent message from ${message.agent}: "${message.content ? message.content.substring(0, 50) : '[No content]'}..."`);
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
                } else {
                    console.log('Unknown message type:', message);
                    addSystemMessage('Received: ' + JSON.stringify(message));
                }
            }

            function createTurnIndicator(agent) {
                document.querySelectorAll('.current-turn-indicator').forEach(el => el.remove());

                const indicator = document.createElement('div');
                indicator.className = 'current-turn-indicator';

                if (agent === "You") {
                    indicator.innerHTML = `<strong>It's your turn!</strong> Please respond to the question.`;

                    const inputArea = document.querySelector('.input-area');
                    inputArea.classList.add('your-turn');

                    messageInput.focus();
                } else {
                    indicator.innerHTML = `<strong>${agent}</strong> is responding...`;

                    const inputArea = document.querySelector('.input-area');
                    inputArea.classList.remove('your-turn');
                }

                messagesContainer.appendChild(indicator);
                scrollToBottom();
            }

            function updateTurnIndicator(agent) {
                userTurn = agent === "You";
                updateUserTurnVisual(userTurn);
                createTurnIndicator(agent);
            }

            function sanitizeInput(input) {
                return input.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, "");
            }

            function sendMessage() {
                const rawMessage = messageInput.value.trim();
                if (!rawMessage) return;

                const message = sanitizeInput(rawMessage);

                if (!message) return;

                if (!userTurn) {
                    const proceed = confirm("It doesn't seem to be your turn to speak. Send your message anyway?");
                    if (!proceed) {
                        return;
                    }
                }

                const formattedMessage = JSON.stringify({
                    type: "user_message",
                    content: message || ""
                });

                if (ws && ws.readyState === WebSocket.OPEN) {
                    try {
                        console.log("Sending message:", formattedMessage);
                        ws.send(formattedMessage);

                        userTurn = false;
                        updateUserTurnVisual(false);
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

            function updateConnectionStatus(status, text) {
                statusDot.className = `status-dot ${status}`;
                statusText.textContent = text;
            }

            function scrollToBottom() {
                messagesContainer.scrollTop = messagesContainer.scrollHeight;
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
                                "content": "restart"
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

            let ws = null;
            let connecting = false;
            let reconnecting = false;
            let userTurn = false;
            let typing = false;

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

                ws.onopen = function() {
                    console.log("WebSocket connection opened");
                    updateConnectionStatus('connected', 'Connected');
                    connecting = false;
                    const startCommand = JSON.stringify({
                        "type": "command",
                        "content": "start"
                    });
                    ws.send(startCommand);
                    startHeartbeat();
                };

                ws.onmessage = function(event) {
                    console.log("Raw WebSocket message received:", event.data);

                    try {
                        const message = JSON.parse(event.data);
                        console.log("Parsed message:", message);
                        if (message.type === "text" && typeof message.content === "object" && message.content.content) {
                            let innerContent = message.content.content;

                            if (typeof innerContent === "string" && innerContent.trim().startsWith("{")) {
                                try {
                                    let parsedInner = JSON.parse(innerContent);
                                    if (parsedInner.type === "command" && parsedInner.content === "start") {
                                        addSystemMessage("STARTED GROUP CHAT");
                                        return;
                                    }
                                } catch (e) {
                                    console.warn("⚠️ Failed to parse inner JSON content:", innerContent);
                                }
                            }
                        }
                        if (message.type === "agent_message") {
                            addAgentMessage(message.agent, message.content);
                            hideTypingIndicator();

                            if (message.agent !== "You") {
                                const calledAgent = findCalledAgent(message.content);
                                console.log("Called agent detected:", calledAgent);

                                if (calledAgent) {
                                    updateTurnIndicator(calledAgent);
                                }
                            }
                        }
                        else if (message.type === "system_message") {
                            addSystemMessage(message.content);
                        }
                        else if (message.type === "agent_list") {
                            console.log("Received agent list:", message.content);
                            updateAgentNames(message.content);
                        }
                        else if (message.type === "user_message") {
                            addAgentMessage("You", message.content);
                            userTurn = false;
                            updateUserTurnVisual(false);
                        }
                        else if (message.type === "terminate") {
                            addSystemMessage("The discussion has ended.");
                        }
                        else if (message.type === "text") {
                            if (message.content && message.content.sender_name) {
                                addAgentMessage(message.content.sender_name, message.content.content);

                                if (message.content.sender_name !== "You") {
                                    const calledAgent = findCalledAgent(message.content.content);
                                    if (calledAgent === "You") {
                                        userTurn = true;
                                        updateUserTurnVisual(true);
                                        messageInput.focus();
                                    }
                                }
                            }
                        }
                        else if (message.type === "error") {
                            addSystemMessage("Error: " + message.message);
                        }
                        else {
                            console.log("Ignoring message:", message);
                        }
                    } catch (e) {
                        console.error("Error handling message:", e);
                    }
                };

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
                addSystemMessage('Welcome!');
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://multiversity.ai",
        f"http://localhost:{PORT}"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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