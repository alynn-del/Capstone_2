# Validation Connection
import os
import re
import json
import warnings

from openai import OpenAI
from detoxify import Detoxify
from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction
from rouge_score import rouge_scorer
from dotenv import load_dotenv
load_dotenv()


client = OpenAI(
    api_key=os.getenv("GEMINI_API_KEY"),
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)

TOXICITY_THRESHOLD = 0.50   # midpoint for crossing over into being a flag
LOW_BLEU = 0.10             # very little lexical overlap
LOW_ROUGE_L = 0.20          # limited shared word sequences
ENTAILMENT_PASS = 0.70      # stricter pass threshold for stronger support

# ------------ Helper: toxicity -------------------
toxicity_model = Detoxify('original')
def evaluate_toxicity(answer: str) -> dict:
    raw_scores = toxicity_model.predict([answer])
    scores = {category: float(values[0]) for category, values in raw_scores.items()}
    flagged = {c: s for c, s in scores.items() if s >= TOXICITY_THRESHOLD}
    return {"passed": not flagged, "scores": scores, "flagged": flagged}


# ------------ Helper: entailment (Gemini as reviewer) ------------------
def check_entailment(answer: str, chunks: list[dict]) -> dict:
    context = "\n\n".join(
        f"Source: {chunk['source']}\n{chunk['content']}"
        for chunk in chunks
    )
    # --- Entailment prompt design -------------------------------------------
        # Task: graded support score (not yes/no) so ENTAILMENT_PASS is tunable.
        # Source/Answer are labeled + delimited so the model never conflates them.
        # Four score bands anchor the scale and keep scoring stable across runs;
        # entailed tied to score>=0.70 so the bool and number can't contradict.
        # "judge the answer, not source similarity" stops long sources inflating score.
        # "Return only JSON" + example keeps the brace-slice/json.loads parse reliable.
    # ------------------------------------------------------------------------
    message = client.chat.completions.create(
        model="gemini-3.5-flash-lite",
        max_tokens=256,
        messages=[
            {
                "role": "user",
                "content": f"""Rate how much the answer is supported by the source text.

Source:
{context}

Answer:
{answer}

Score bands (judge the answer, not source similarity):
- 0.90-1.0: exact/near-exact match
- 0.75-0.89: faithful paraphrase, meaning unchanged
- 0.40-0.74: partially supported
- below 0.40: contradicts source or adds unsupported claims
entailed = true only if score >= 0.70.

Return only JSON: {{"entailed": true, "score": 0.95, "reason": "..."}}""",
            }
        ],
    )

    raw = message.choices[0].message.content.strip()
    raw = raw[raw.find("{"):raw.rfind("}") + 1]
    result = json.loads(raw)

    return {
        "entailed": bool(result["entailed"]),
        "score": float(result["score"]),
        "reason": result["reason"],
        "input_tokens": message.usage.prompt_tokens,
        "output_tokens": message.usage.completion_tokens,
    }

# ------------ Helper: lexical overlap (BLEU / ROUGE-L) ------------------
def _overlap_scores(answer: str, chunks: list[dict]) -> tuple[float, float]:
    answer_tokens = re.findall(r"\w+", answer.lower())
    smoother = SmoothingFunction().method1
    scorer = rouge_scorer.RougeScorer(["rouge1", "rougeL"], use_stemmer=True)

    bleu_scores = []
    rouge_l_scores = []

    for chunk in chunks:
        source = chunk["content"]
        source_tokens = re.findall(r"\w+", source.lower())

        bleu_scores.append(
            sentence_bleu([source_tokens], answer_tokens, smoothing_function=smoother)
        )
        rouge_l_scores.append(scorer.score(source, answer)["rougeL"].fmeasure)

    return max(bleu_scores), max(rouge_l_scores)


#-------------Combined qualitative validation function----------------
def validate_qualitative(answer: str, chunks: list[dict]) -> dict:
    
    # ---------- missing inputs ----------
    if not answer or not chunks:
        warning = "Missing answer or source chunks"
        return {
            "is_grounded": False,
            "refused_to_answer": False,
            "sources_cited": [],
            "bleu": 0.0,
            "rouge_l": 0.0,
            "entailed": False,
            "entailment_score": 0.0,
            "input_tokens": 0,
            "output_tokens": 0,
            "flag": True,
            "warning": warning,
        }

    failures = []

    # ---------- grounding/citing sources ----------
    sources_cited = [
        chunk["source"]
        for i, chunk in enumerate(chunks)
        if f"Source {i+1}" in answer
    ]
    grounded = len(sources_cited) > 0
    refused = "cannot find" in answer.lower()
    if not grounded and not refused:
        failures.append("Response may not be grounded in source documents")

    # ---------- toxicity ----------
    toxicity = evaluate_toxicity(answer)
    if not toxicity["passed"]:
        failures.append(
            f"Response exceeded the toxicity threshold ({', '.join(toxicity['flagged'])})"
        )

    # ---------- overlap + entailment ----------
    bleu, rouge_l = _overlap_scores(answer, chunks)
    entailment = check_entailment(answer, chunks)
    entailed = bool(entailment.get("entailed", False))
    entailment_score = entailment["score"]

    low_overlap = bleu < LOW_BLEU or rouge_l < LOW_ROUGE_L
    # Good overlap passes. If overlap is low, the answer still passes when it is
    # well supported (paraphrase) or the reviewer marks it entailed.
    supported = (not low_overlap) or entailment_score >= ENTAILMENT_PASS or entailed
    if not supported:
        failures.append(
            f"Answer is not grounded in sources "
            f"(bleu={round(bleu, 4)}, rouge_l={round(rouge_l, 4)}, "
            f"entailment_score={entailment_score})"
        )

    # ---------- single flag / warning contract ----------
    flag = len(failures) > 0
    warning = "; ".join(failures) if flag else None

    return {
        "is_grounded": grounded,
        "refused_to_answer": refused,
        "sources_cited": sources_cited,
        "bleu": round(bleu, 4),
        "rouge_l": round(rouge_l, 4),
        "entailed": entailed,
        "entailment_score": entailment_score,
        "reason": entailment["reason"],
        "input_tokens": entailment["input_tokens"],
        "output_tokens": entailment["output_tokens"],
        "flag": flag,
        "warning": warning,
    }


#------------Combined quantitative validation function-----------
def validate_quantitative(answer: str, sql: str, validation_status: str) -> dict:
    failures = []

    # ---------- execution status (SQL already checked upstream in quantitative) ----------
    sql_validated = validation_status == "PASSED"
    sql_blocked = validation_status == "FAILED"
    execution_error = validation_status == "ERROR"
    if not sql_validated:
        failures.append(f"SQL validation status: {validation_status}")

    # ---------- toxicity on the LLM synopsis ----------
    toxicity = evaluate_toxicity(answer) if answer else {"passed": True, "flagged": {}}
    if not toxicity["passed"]:
        failures.append(
            f"Response exceeded the toxicity threshold ({', '.join(toxicity['flagged'])})"
        )

    # ---------- single flag / warning contract ----------
    flag = len(failures) > 0
    warning = "; ".join(failures) if flag else None

    return {
        "sql_validated": sql_validated,
        "sql_blocked": sql_blocked,
        "execution_error": execution_error,
        "flag": flag,
        "warning": warning,
    }