# testing claude connection
import anthropic
from dotenv import load_dotenv
load_dotenv()

client = anthropic.Anthropic()
message = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=50,
    messages=[{"role": "user", "content": "Say hello in one sentence."}]
)
print(message.content[0].text)
print(f"Input tokens: {message.usage.input_tokens}")
print(f"Output tokens: {message.usage.output_tokens}")
