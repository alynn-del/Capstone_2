from openai import OpenAI
import os
from dotenv import load_dotenv
from agents import qualitative, quantitative
from validation.validator import validate_qualitative, validate_quantitative
from tokenomics.logger import log
load_dotenv()

client = OpenAI(
    api_key=os.getenv("GEMINI_API_KEY"),
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

def classify(query: str) -> str:

    # --- Classifier prompt design -------------------------------------------
        # Closed set of 3 labels stated up front → output maps directly to a route,
        # Each label defined by the data it needs (docs vs. SQL), not keywords.
        # "both" spelled out explicitly, else the model just picks one.
        # max_tokens=10 → a label is 1-2 tokens; hard cap bounds cost on a call made for every query.
    # ------------------------------------------------------------------------
    message = client.chat.completions.create(
        model="gemini-3.5-flash-lite",
        max_tokens=10,
        messages=[{
            "role": "user",
            "content": f"""Classify this query as exactly one of: qualitative, quantitative, both.

qualitative = questions about policies, processes, procedures, explanations, documentation
quantitative = questions about numbers, metrics, trends, comparisons, SQL-queryable data
both = questions that need both text document search and data analysis through SQL querying

Query: {query}

Reply with one word only: qualitative, quantitative, or both."""
        }]
    )
    route = message.choices[0].message.content.strip().lower()
    log(query, "manager-classifier",
        message.usage.prompt_tokens, message.usage.completion_tokens)
    return route if route in ["qualitative", "quantitative", "both"] else "qualitative"

def run(query: str):
    print(f"\nQuery: {query}")
    route = classify(query)
    print(f"Route: {route}")

    qual_result = None
    quant_result = None

    if route in ["qualitative", "both"]:
        qual_result = qualitative.run(query)

        #--------Validate before ever returning to user--------
        validation = validate_qualitative(qual_result["answer"], qual_result["chunks"])

        #-------Log tokenomics (generation + validation entailment tokens)--------
        total_input = qual_result["input_tokens"] + validation.get("input_tokens", 0)
        total_output = qual_result["output_tokens"] + validation.get("output_tokens", 0)
        log(query, "qualitative", total_input, total_output)
        
        #-------Print validation results--------
        if validation["flag"]:
            print("\n⚠️  This response was withheld for your protection.")
            print(f"\nThe generated answer did not pass validation ({validation['warning']}) "
                  "— it may contain inaccurate, unsupported, or inappropriate content, "
                  "so it has not been shown.")
        else:
            print("\n✅  Qualitative answer validated.")
            #------Only print full results when validated--------
            print(f"\n[Qualitative]\n{qual_result['answer']}")

        

    if route in ["quantitative", "both"]:
        quant_result = quantitative.run(query)
        
        #-------Validate before ever returning to user--------
        validation = validate_quantitative(
            quant_result["answer"],
            quant_result["sql"],
            quant_result["validation"]
        )

        #-------Log tokenomics--------
        log(query, "quantitative", quant_result["input_tokens"], quant_result["output_tokens"])
        
        #-------Print validation results--------
        if validation["flag"]:
            print(f"\n⚠️  VALIDATION ERROR: {validation['warning']}")
            msg = quant_result["sql"].split("'", 1)[-1].rsplit("'", 1)[0] if "'" in quant_result["sql"] else "I can't answer that from the available data."
            print(f"Error message: {msg}")
        else:
            print("\n✅  Quantitative answer validated.")
            #------Only print full results when validated--------
            print(f"\n[Quantitative]\n{quant_result['answer']}")
            print(f"SQL used: {quant_result['sql']}")

        