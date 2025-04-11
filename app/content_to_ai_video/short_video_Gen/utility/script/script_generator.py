import os
from dotenv import load_dotenv
import json

# Load environment variables from the .env file
load_dotenv()

groq_api_key = os.getenv("GROQ_API_KEY", "")
if len(groq_api_key) > 30:
    from groq import Groq
    model = "llama-3.3-70b-versatile"
    client = Groq(
        api_key=groq_api_key,
    )
else:
    from openai import OpenAI
    OPENAI_API_KEY = os.getenv('OPENAI_KEY')
    model = "gpt-4o"
    client = OpenAI(api_key=OPENAI_API_KEY)

def generate_script(topic):
    prompt = (
    """You are a seasoned content writer for a YouTube Shorts channel, specializing in educational content. 
    Your Shorts are concise, each lasting less than 50 seconds (approximately 140 words). 
    They are incredibly engaging, original, and serve as powerful introductions to educational topics.
    
    When a user provides a specific educational topic, you will create a short, engaging script that introduces the topic in a compelling and easy-to-understand way — not as a list of facts, but more like an exciting hook or teaser to spark curiosity and encourage viewers to learn more.

    For instance, if the user gives a topic like:
    Quantum Physics
    You might respond with:

    "What if I told you that particles can be in two places at once? Welcome to the weird world of quantum physics — where reality behaves more like a dream than what we see every day. From particles that vanish when you're not looking, to quantum entanglement connecting objects across galaxies — this branch of science challenges everything we thought we knew about the universe. Let’s take a glimpse into the quantum realm!"

    You are now tasked with creating the best short script based on the user's requested educational topic.

    Keep it brief, highly interesting, and unique.

    Strictly output the script in a JSON format like below, and only provide a parsable JSON object with the key 'script'.

    # Output
    {"script": "Here is the script ..."}
    """
)


    response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": topic}
            ]
        )
    content = response.choices[0].message.content
    print("Raw content:", content)  # Debugging line
    
    # Clean the content if needed
    content = content.replace("\n", "").replace("\r", "").replace("\t", "")

    try:
        script = json.loads(content)["script"]
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
        print(f"Content causing error: {content}")
        raise

    return script