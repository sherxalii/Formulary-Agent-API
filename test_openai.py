import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

try:
    response = client.embeddings.create(
        input="test",
        model="text-embedding-3-large"
    )
    print("SUCCESS: OpenAI API is working!")
except Exception as e:
    print(f"FAILURE: OpenAI API is still failing: {e}")
