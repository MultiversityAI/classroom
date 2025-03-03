import os
import json
import re
import random
import autogen
from autogen import UserProxyAgent, GroupChat, GroupChatManager, ConversableAgent
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

config_path = "CONFIG_LIST.json"
config_list = autogen.config_list_from_json(config_path)

for config in config_list:
    if config["api_key"] is None:
        config["api_key"] = api_key

llm_config = {"config_list": config_list}

# Load student data
with open("students.json", "r") as f:
    student_data = json.load(f)

# Add instructions about calling on others and reinforcing own identity
for student in student_data:
    student["system_message"] += """

When appropriate, end your contributions by calling on a specific classmate or the teacher by name.
For example: "What do you think about this, Bianca?" or "Teacher, what's your perspective on this?"

IMPORTANT: Always speak in the first person as yourself. Never refer to yourself in the third person.
You are {0}, responding as "I" - not talking about {0} as if they were someone else.

Be very careful not to respond to questions directed to others. If someone else is called upon by name,
wait for them to respond.
""".format(student["name"])

# Create student agents
student_agents = []
for student in student_data:
    student_agents.append(
        ConversableAgent(
            name=student["name"],
            system_message=student["system_message"],
            description=student["description"],
            llm_config=llm_config
        )
    )

# Create user proxy
user_proxy = UserProxyAgent(
    name="You",
    human_input_mode="ALWAYS",
    system_message="You are participating in a classroom discussion. Share your thoughts when called upon.",
    description="human user who interacts with agentic experiences"
)

# Create teacher agent
teacher = ConversableAgent(
    name="Teacher",
    system_message="""You are a knowledgeable teacher leading an office hours discussion with a small group of students.

    if students need a problem to work on in relation to the topic, provide the following question: 
    
    A scientist is studying blood flow in the aorta of five
    different animal species of similar size and age. 
    She found that the composition of the blood was identical
    in each animal as well as the diameter of their aortas, 
    but the rate of blood flow through the aorta was different. 
    The scientist measured the following pressures 
    at the beginning (i.e., ascending aorta) 
    and near the end (i.e., abdominal aorta) of the aorta.
    
    The pressures for each animal are as follows:
        Zebra: Start pressure = 210, End pressure = 150
        Camel: Start pressure = 200, End pressure = 180
        Elk: Start pressure = 200, End pressure = 160
        Water Buffalo: Start pressure = 150, End pressure = 130
        Sitka Deer: Start pressure = 100, End pressure = 30
        
    Which animal has the greatest flow rate (L/min) of blood through the aorta?
    Explain why the animal you selected has the greatest flow rate (L/min) of blood through the aorta.
 

    Your responsibilities include:
    1. Always aim to facilitate deeper learning rather than simply providing correct answers.
    2. Calling on specific students by name to participate
    3. Guiding the discussion to explore various perspectives
    4. Ensuring all students get a chance to speak
    5. Encouraging deeper critical thinking through follow-up questions
    6. Summarizing key points at appropriate intervals
    7. Never give away answers or provide hints that indicate correct answers without student reasoning.
    8. Focus on eliciting student thinking and reasoning.
    9. Use constructivist approaches to challenge misconceptions.
    10. Provide factual information only for simple recall errors, not to reveal answers.
    11. Encourage metacognition by asking students to explain their thought processes.
    12. Offer more challenging problems when students demonstrate understanding.
    13. Use positive reinforcement when students show progress or correct understanding.


    Also ensure the human user (named "You") gets opportunities to participate.

    End your messages by clearly calling on a specific student or the human user by name
    to respond next. For example: "What do you think about this, Alvin?" or "Do you have
    any thoughts on this topic, You?"
    """,
    description="The teacher who facilitates the classroom discussion with expertise on the topic",
    llm_config=llm_config
)

# More comprehensive function to find who was called on in the last message
def find_next_speaker(last_message_content, agent_names):
    # Check if "human user" is mentioned (special case)
    if "human user" in last_message_content:
        return "You"

    # Check for direct mentions at the end of the message
    sentences = re.split(r'[.!?]\s+', last_message_content)
    sentences = [s for s in sentences if s.strip()]

    if sentences:
        last_two_sentences = sentences[-2:] if len(sentences) >= 2 else sentences
        for sentence in last_two_sentences:
            for name in agent_names:
                # Exact name match with word boundaries
                pattern = r'\b{}\b'.format(re.escape(name))
                if re.search(pattern, sentence):
                    return name

    # Check for specific calling patterns
    patterns = [
        r"(?:^|\W)(Alvin|Bianca|Charlie|You|Teacher)(?:,|\.|\?|!|\s).*?\?$",
        r"(?:^|\W)(Alvin|Bianca|Charlie|You|Teacher)(?:,|\.|\?|!|\s).*thoughts",
        r"(?:^|\W)(Alvin|Bianca|Charlie|You|Teacher)(?:,|\.|\?|!|\s).*think",
        r"Let's hear from\s+(Alvin|Bianca|Charlie|You|Teacher)",
        r"(Alvin|Bianca|Charlie|You|Teacher),\s+would you",
        r"What (?:do|about|are) (?:you|your).*,\s+(Alvin|Bianca|Charlie|You|Teacher)",
        r"(Alvin|Bianca|Charlie|You|Teacher),\s+what",
        r"What do you think,?\s+(Alvin|Bianca|Charlie|You|Teacher)",
        r"Do you (?:have|think).*,?\s+(Alvin|Bianca|Charlie|You|Teacher)",
        r"How about you,?\s+(Alvin|Bianca|Charlie|You|Teacher)",
        r"(Alvin|Bianca|Charlie|You|Teacher),\s+(?:do|can|could) you",
        r"(?:Do|Can|Could|Would) (Alvin|Bianca|Charlie|You|Teacher)",
        r"I'd like to hear from\s+(Alvin|Bianca|Charlie|You|Teacher)",
        r"(Alvin|Bianca|Charlie|You|Teacher)\s+(?:should|could|would) (?:you|your)",
        r"hear (?:your|) thoughts,?\s+(Alvin|Bianca|Charlie|You|Teacher)",
        r"ask\s+(Alvin|Bianca|Charlie|You|Teacher)",
    ]

    for pattern in patterns:
        matches = re.findall(pattern, last_message_content, re.IGNORECASE)
        if matches:
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]  # Extract from tuple if needed
                if match in agent_names:
                    return match

    # Special handling for "human user" or similar variations
    patterns = [
        r'\bYou\b',
        r'human user',
    ]

    for pattern in patterns:
        if re.search(pattern, last_message_content, re.IGNORECASE):
            return "You"

# Improved custom speaker selection function with stricter adherence
def custom_speaker_selection(last_speaker, group_chat):
    # List of all agent names
    agent_names = [agent.name for agent in group_chat.agents]

    # If no messages yet (beginning of conversation), choose the Teacher
    if len(group_chat.messages) <= 1:  # Just the initial prompt
        return next(agent for agent in group_chat.agents if agent.name == "Teacher")

    # Get the last message content
    last_message = group_chat.messages[-1]
    last_message_content = last_message.get("content", "")

    # Find if a specific participant was called upon (by any speaker)
    called_participant = find_next_speaker(last_message_content, agent_names)

    if called_participant:
        # Return the called participant agent
        return next(agent for agent in group_chat.agents if agent.name == called_participant)

    # Otherwise pick a random student (not the last speaker)
    available_speakers = [agent for agent in group_chat.agents if agent != last_speaker]
    if available_speakers:
        return random.choice(available_speakers)
    else:
        return random.choice(group_chat.agents)

# All participants
all_participants = [teacher] + student_agents + [user_proxy]

# Create the group chat with custom speaker selection
group_chat = GroupChat(
    agents=all_participants,
    messages=[],
    max_round=30,
    speaker_selection_method=custom_speaker_selection,
    allow_repeat_speaker=False,
    send_introductions=True
)

# Create the group chat manager
chat_manager = GroupChatManager(
    groupchat=group_chat,
    name="chat_manager",
    llm_config=llm_config,
)

# Topic for discussion
default_topic = "Bulk flow in physiology"

# Initial prompt
initial_prompt = f"""
   Start by asking the user whether they have a problem they want to work on with the group or if there is a specific topic they'd like help with.
    Provide a question appropriate for an undergraduate level class on the topic if they mention a topic they'd like help with but do not have a specific question or problem to begin working on. 
    If the user has a question ready to go, allow them to pose it to the group and guide the discussion as needed. 
    Intervene sparingly or when called upon so that students can maximize their learning through discussion. 
    Begin the classroom discussion now.
"""

# Start the group chat
result = user_proxy.initiate_chat(
    chat_manager,
    message=initial_prompt
)

print("Classroom discussion concluded!")