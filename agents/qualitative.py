import os
import chromadb
from openai import OpenAI
from sentence_transformers import SentenceTransformer, util
from dotenv import load_dotenv
load_dotenv()

client = OpenAI(
        api_key=os.getenv("GEMINI_API_KEY"),
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
    )
model = SentenceTransformer("all-MiniLM-L6-v2")

def retrieve(query: str, top_k: int = 5) -> list[dict]:
    chroma = chromadb.PersistentClient(path="./data/chroma")
    collection = chroma.get_collection("enterprise-docs")
    embedding = model.encode([query]).tolist()
    results = collection.query(query_embeddings=embedding, n_results=top_k)
    return [
        {
            "content": doc,
            "source": meta["source"],
            "chunk": meta["chunk"]
        }
        for doc, meta in zip(results["documents"][0], results["metadatas"][0])
    ]


def build_prompt(query: str, chunks: list[dict]) -> str:
      # --- Document answer prompt design -------------------------------------------
        # Context: number each chunk + prefix its source name 
        # "using ONLY the context" → blocks pretrained-knowledge answers that the entailment check would later flag.
        # Fixed refusal string → detectable fallback for out-of-scope questions instead of a hallucinated guess.
        # "cite source number(s) + name" → produces the citations the grounding check looks for and lets the user trace each claim.
        # "no markdown" → printed raw to the CLI, where *, #, | would show literally.
    # ------------------------------------------------------------------------
    context = ""
    for i, chunk in enumerate(chunks):
        context += f"[Source {i+1}: {chunk['source']}]\n{chunk['content']}\n\n"

    return f"""You are a helpful enterprise documentation assistant.
Answer the question using ONLY the context provided below.
If the answer is not in the context, say "I cannot find this information in the provided documents."
Always cite the source number(s) you used as well as the name of the source written at the top of each source.
The final output should contain no markdown formatting.

CONTEXT:
{context}

QUESTION: {query}

ANSWER:"""


def run(query: str) -> dict:
    chunks = retrieve(query)
    prompt = build_prompt(query, chunks)
    message = client.chat.completions.create(
        model="gemini-3.5-flash-lite",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )

    #-------Break down before returning--------
    answer = message.choices[0].message.content.strip()
    usage = message.usage

    input_tokens = usage.prompt_tokens
    output_tokens = usage.completion_tokens

    return {
        "answer": answer,
        "chunks": chunks,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }

