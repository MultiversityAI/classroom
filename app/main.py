import json
import logging
import re
import uvicorn
import asyncio

import autogen
from autogen import UserProxyAgent, GroupChat, GroupChatManager, ConversableAgent
from autogen.io.websockets import IOWebsockets
from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import logging

logging.basicConfig(level=logging.INFO)

def console_log(message):
    logging.info(message)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

config_list = autogen.config_list_from_json("CONFIG_LIST.json")

llm_config = {"config_list": config_list, "stream": False}

PORT = 8001
discussion_active = False

student_data = [
    {
        "description": "Alvin is a curious AI student who pieces together information, sometimes making accurate connections and other times forming misconceptions that need correction.",
        "name": "Alvin",
        "system_message": "You are Alvin, an undergraduate student participating in collaborative group work during office hours.\n\nYour responses should realistically reflect the prior knowledge, conceptual difficulties, misconceptions, and social behaviors typical of undergraduate learners engaged in small group work.\n\n## Knowledge Representation\n- Display incomplete but developing disciplinary knowledge.\n- Incorporate occasional misconceptions common to novice learners in the field.\n\n## Metacognitive Patterns\n- Demonstrate varying levels of self-awareness about knowledge limitations.\n- Show occasional overconfidence in some areas and underconfidence in others.\n- Exhibit strategic thinking about completing assignments efficiently.\n\n## Social Dynamics in Group Settings\n- Participate in idea negotiation processes with peers.\n- Occasionally advocate strongly for personal viewpoints.\n\n## Communication Style\n- Use informal academic language mixed with some discipline-specific terminology.\n- Occasionally use hedging language when uncertain ('I think', 'maybe', 'probably').\n- Occasionally reference personal experiences as evidence.\n- Ask clarifying questions when encountering unfamiliar concepts.\n\n## Personal Characteristics of Alvin\nAlvin has always been the type to light up when discussing new ideas. He is the student who gets genuinely excited about making connections between concepts. Growing up, he was the kind of kid who asked, 'But why?' a dozen times in a row, much to the exhaustion of his teachers and parents. Now, as a university student, Alvin thrives in group settings where brainstorming and open-ended discussions happen. He is the one who energizes the room, throwing out half-formed ideas that sometimes turn out to be brilliant and other times need some refining. He is eager to learn from others and does not mind being wrong—as long as the discussion leads somewhere interesting."
    },
    {
        "description": "Bianca is an AI student who confidently presents common misconceptions, providing opportunities for discussion and correction.",
        "name": "Bianca",
        "system_message": "You are Bianca, an undergraduate student participating in collaborative group work during office hours.\n\nYour responses should realistically reflect the prior knowledge, conceptual difficulties, misconceptions, and social behaviors typical of undergraduate learners engaged in small group work.\n\n## Knowledge Representation\n- Display incomplete but developing disciplinary knowledge.\n- Incorporate occasional misconceptions common to novice learners in the field.\n\n## Metacognitive Patterns\n- Demonstrate varying levels of self-awareness about knowledge limitations.\n- Show occasional overconfidence in some areas and underconfidence in others.\n- Exhibit strategic thinking about completing assignments efficiently.\n\n## Social Dynamics in Group Settings\n- Participate in idea negotiation processes with peers.\n- Occasionally advocate strongly for personal viewpoints.\n\n## Communication Style\n- Use informal academic language mixed with some discipline-specific terminology.\n- Occasionally use hedging language when uncertain ('I think', 'maybe', 'probably').\n- Occasionally reference personal experiences as evidence.\n- Ask clarifying questions when encountering unfamiliar concepts.\n\n## Personal Characteristics of Bianca\nBianca grew up loving debates and discussions. Whether it was arguing the finer points of a book in literature class or challenging a math teacher's shortcut method, she developed a strong sense of confidence in her ideas. She believes that the best way to learn is to test every assumption—which is why she enjoys pushing back in discussions, even when she is not completely sure she is right. Now, in university, Bianca is the group member who keeps everyone sharp. She is great at structuring conversations, making sure the group does not just agree too quickly but actually understands the topic. She plays devil's advocate not to be difficult, but because she believes that real learning happens when ideas are examined from every angle."
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
                iostream.raw_send(json.dumps({
                    "type": "system_message",
                    "content": "The discussion has concluded. See you next time!"
                }))
            except Exception as e:
                console_log(f"🚨 Error sending system message: {e}")
        return None

    if re.search(r"\bsee you next time\b", last_content, re.IGNORECASE):
        if iostream:
            try:
                iostream.raw_send(json.dumps({
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
                iostream.raw_send(json.dumps({
                    "type": "system_message",
                    "content": f"It's {next_speaker}'s turn to speak."
                }))
            except Exception as e:
                console_log(f"🚨 Error sending next speaker notification: {e}")

        return next_agent

    return next(agent for agent in group_chat.agents if agent.name == "Teacher")

discussion_active = False

# Add this method to the IOWebsockets class
def raw_send(self, message):
    """Send a raw message without trying to convert to model_dump_json"""
    if hasattr(self.websocket, 'send_text'):
        asyncio.run(self.websocket.send_text(message))
    else:
        self.websocket.send(message)

# Monkey patch the IOWebsockets class
IOWebsockets.raw_send = raw_send

async def on_connect(iostream: IOWebsockets) -> None:
    """Handle new WebSocket connection and start classroom discussion."""
    global discussion_active

    console_log(f"🚀🚀🚀 [WebSocket] New client connected from: {iostream}")

    try:
        console_log("Waiting for initial message...")

        await asyncio.sleep(2)

        try:
            message = {
                "type": "system_message",
                "content": "Connection established! Waiting for your input..."
            }
            iostream.raw_send(json.dumps(message))
            console_log("✅ Sent test system message")
        except Exception as e:
            console_log(f"❌ Error sending test message: {e}")

        initial_msg = iostream.input()
        console_log(f"👋 Initial message received from client: {initial_msg}")


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
            iostream.raw_send(json.dumps({
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
            iostream.raw_send(json.dumps(agent_list_msg))
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
                iostream.raw_send(json_str)
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
            await user_proxy.initiate_chat(chat_manager, message={"type": "start_message", "content": start_msg})
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
            iostream.raw_send(error_json)
            console_log(f"DEBUG: Sent error message: {error_json}")
        except Exception as ws_error:
            console_log(f"WebSocket send error in on_connect: {ws_error}")

    finally:
        discussion_active = False
        console_log("Classroom discussion has concluded.")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    global discussion_active

    if discussion_active:
        await websocket.send_text(json.dumps({"type": "system_message", "content": "A discussion is already active."}))
        await websocket.close()
        return

    discussion_active = True

    iostream = IOWebsockets(websocket)
    # Add raw_send method to this instance
    iostream.raw_send = lambda message: websocket.send_text(message)

    teacher = ConversableAgent(
        name="Teacher",
        system_message="You are the teacher leading a structured classroom discussion.",
        llm_config=llm_config,
    )

    students = [
        ConversableAgent(
            name=student["name"],
            system_message=student["system_message"],
            llm_config=llm_config,
        )
        for student in student_data
    ]

    user_proxy = UserProxyAgent(
        name="You",
        human_input_mode="ALWAYS",
        system_message="You're the human participant in this discussion.",
        code_execution_config=False,
        is_termination_msg=lambda x: isinstance(x, str) and x.lower().strip() == "exit",
    )

    all_agents = [teacher] + students + [user_proxy]

    group_chat = GroupChat(
        agents=all_agents,
        messages=[],
        max_round=30,
        speaker_selection_method="round_robin",
        allow_repeat_speaker=False,
    )

    chat_manager = GroupChatManager(
        groupchat=group_chat,
        name="chat_manager",
        llm_config=llm_config,
    )

    try:
        initial_message = iostream.input()

        if isinstance(initial_message, str):
            initial_data = json.loads(initial_message)
            if initial_data.get("type") == "command" and initial_data.get("content") == "start":
                await websocket.send_text(json.dumps({"type": "system_message", "content": "Discussion started!"}))

                def custom_input(_):
                    return iostream.input()

                user_proxy.get_human_input = custom_input

                await chat_manager.a_initiate_chat(
                    user_proxy,
                    message="Let's begin today's discussion! Teacher, please introduce the topic.",
                )
        else:
            await websocket.send_text(json.dumps({"type": "system_message", "content": "Invalid initial message."}))

    except Exception as e:
        logging.error(f"Error during discussion: {e}")
        await websocket.send_text(json.dumps({"type": "system_message", "content": f"Error: {str(e)}"}))

    finally:
        discussion_active = False
        await websocket.send_text(
            json.dumps({"type": "system_message", "content": "Discussion ended. See you next time!"})
        )
        await websocket.close()

app.mount("/", StaticFiles(directory="website_files/templates", html=True), name="static")

if __name__ == "__main__":
    def sync_on_connect(iostream):
        import asyncio
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(on_connect(iostream))
        except Exception as e:
            logging.error(f"Error in on_connect: {e}")
            import traceback
            logging.error(traceback.format_exc())

    with IOWebsockets.run_server_in_thread(on_connect=sync_on_connect, host='0.0.0.0', port=8080):
        logging.info("🚀 WebSocket server started on ws://0.0.0.0:8080")
        uvicorn.run(app, host="0.0.0.0", port=PORT)