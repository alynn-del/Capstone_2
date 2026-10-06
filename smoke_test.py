# smoke_test.py
# import anthropic
# from dotenv import load_dotenv
# load_dotenv()

# client = anthropic.Anthropic()
# message = client.messages.create(
#     model="claude-sonnet-4-6",
#     max_tokens=50,
#     messages=[{"role": "user", "content": "Say hello in one sentence."}]
# )
# print(message.content[0].text)
# print(f"Input tokens: {message.usage.input_tokens}")
# print(f"Output tokens: {message.usage.output_tokens}")

import os
from pathlib import Path
from dotenv import load_dotenv, find_dotenv

path = find_dotenv()
print("1. .env file found at:", path if path else "NOT FOUND")

load_dotenv()
key = os.environ.get("ANTHROPIC_API_KEY")
print("2. Key loaded:", bool(key))
print("3. Starts with sk-ant-:", str(key).startswith("sk-ant-"))
print("4. Length:", len(key) if key else 0)