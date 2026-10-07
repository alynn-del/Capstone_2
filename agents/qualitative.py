import os
import chromadb
from openai import OpenAI
from sentence_transformers import SentenceTransformer
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

# validation here 
def build_prompt(query: str, chunks: list[dict]) -> str:
    context = ""
    for i, chunk in enumerate(chunks):
        context += f"[Source {i+1}: {chunk['source']}]\n{chunk['content']}\n\n"

    return f"""You are a helpful enterprise documentation assistant.
Answer the question using ONLY the context provided below.
If the answer is not in the context, say "I cannot find this information in the provided documents."
Always cite the source number(s) you used.

CONTEXT:
{context}

QUESTION: {query}

ANSWER:"""

def run(query: str) -> dict:
    chunks = retrieve(query)
    prompt = build_prompt(query, chunks)
    message = client.chat.completions.create(
        model="gemini-3.6-flash",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )
    # validate answer here TODO
    return {
        "answer": message.choices[0].message.content.strip(),
        "chunks": chunks,
        "input_tokens": getattr(message.usage, 'input_tokens', 0),
        "output_tokens": getattr(message.usage, 'output_tokens', 0)
    }



def test_qualitative_agent() -> None:
    query = "What is our company's security policy?"

    print("=" * 60)
    print(f"Question: {query}")
    print("=" * 60)

    try:
        chroma = chromadb.PersistentClient(path="./data/chroma")
        collection = chroma.get_collection("enterprise-docs")

        document_count = collection.count()
        print(f"Documents in collection: {document_count}")

        if document_count == 0:
            print("Validation: FAILED")
            print("The enterprise-docs collection is empty.")
            return

        result = run(query)
        chunks = result.get("chunks", [])
        answer = result.get("answer", "").strip()

        if not chunks:
            print("Validation: FAILED")
            print("No chunks were retrieved.")
            return

        if not answer:
            print("Validation: FAILED")
            print("The agent returned no answer.")
            return

        print("\nRetrieved chunks:")
        for chunk in chunks:
            print(f"- {chunk['source']} | chunk {chunk['chunk']}")

        print("\nAgent answer:")
        print(answer)

        print("\nValidation: PASSED")

    except Exception as error:
        print("Validation: ERROR")
        print(error)


if __name__ == "__main__":
    test_qualitative_agent()