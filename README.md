# Capstone 2: Multi-Agent RAG System with Gemini

## Architecture Diagram
```
                      User Query (CLI)
                            │
                            ▼
                   ┌─────────────────┐
                   │  Manager Agent  │
                   └─────────────────┘
             classifies query → qualitative / quantitative / both
                            │
            ┌───────────────┴───────────────┐
            ▼                                ▼
 ┌──────────────────┐            ┌────────────────────┐
 │ Qualitative Agent│            │ Quantitative Agent │
 │                  │            │                    │
 │ • Vector DB      │            │ • SQLite DB        │
 │   (ChromaDB)     │            │ • NL → SQL         │
 │ • Semantic search│            │ • Query execution  │
 │ • Gemini for     │            │ • Gemini for       │
 │   generation     │            │   interpretation   │
 └──────────────────┘            └────────────────────┘
            │                                │
            └───────────────┬────────────────┘
                            ▼
           ┌──────────────────────────────────┐
           │         Validation Layer         │
           │                                  │
           │ Qualitative:                     │
           │  • Source citation check         │
           │  • BLEU / ROUGE-L overlap        │
           │  • Entailment score (Gemini)     │
           │  • Toxicity (Detoxify)           │
           │                                  │
           │ Quantitative:                    │
           │  • SQL validation status         │
           │  • Toxicity (Detoxify)           │
           └──────────────────────────────────┘
             flags issues before user sees them
                            │
                            ▼
           ┌──────────────────────────────────┐
           │        Tokenomics Logger         │
           └──────────────────────────────────┘
             logs token usage + cost per query
             to tokenomics_log.jsonl
             (includes Gemini validation tokens)
                            │
                            ▼
                    Response to User
```



## Usage Instructions
### Setup

You'll need **Python 3.10+**, **Git**, and a **Google Gemini API key** (from https://ai.google.dev). The system uses Gemini to classify your question, generate answers, and validate them, so it won't run without a key.

**1. Clone and enter the project:**
```bash
git clone https://github.com/alynn-del/Capstone_2.git
cd Capstone_2
```
`git clone` downloads the project into a new `Capstone_2` folder; `cd` moves you into it. Run every command below from inside this folder.

**2. Set up a virtual environment and install dependencies:**
```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```
The virtual environment keeps this project's packages separate from the rest of your system. Once it's active, your prompt starts with `(.venv)` — if you don't see that, the activate step didn't run. You'll activate it again each time you come back to the project; type `deactivate` to exit it.

**3. Add your API key** — create a `.env` file in the project folder:
```bash
echo "GEMINI_API_KEY=your_key_here" > .env
```
Swap `your_key_here` for your actual key. Keep the name exactly `GEMINI_API_KEY` — that's what the code looks for. This file holds a secret, so don't commit or share it.

### Running

```bash
python main.py
```

The first run downloads a toxicity model used for validation (one time, be patient — you'll see progress bars). It's cached afterward, so later runs start instantly. When ready, you'll see:
```
Spoonful Enterprise RAG System
Type 'exit' to quit.
```

### Asking questions

Type a question and press Enter. Each question is automatically routed to a specialized agent — qualitative, quantitative, or both — based on what it's asking for. You'll see the chosen route printed above the answer.

- **Qualitative** — for policies, processes, and explanations drawn from company documents. Try: `What is our company's security policy?`
    - Pulls from source materials provided by the company, such as `customer_success_strategy.txt` and `security_policy.txt`, and cites what it used.
- **Quantitative** — for numbers, metrics, and trends. Try: `Show me monthly revenue trends`
    - Queries a SQL database and returns the data along with the SQL query that produced it, so you can verify the result.
- **Both** — for questions that need documents *and* data together. Try: `How does our employee satisfaction compare to industry standards and what policies might impact this?`
    - Runs both agents and shows each result separately.

Every answer is checked before it reaches you and marked with one of:

- ✅ **passed validation** — grounded in its sources, well-supported, and clean.
- ⚠️ **may be unreliable** — not grounded in the sources, unsupported by them, or flagged for toxic language. The answer does not show to the user only the validation warning.

Type `exit` to quit.

### Troubleshooting

- **`ModuleNotFoundError`** — the virtual environment isn't active (no `(.venv)` in your prompt) or dependencies didn't install. Re-run step 2.
- **Authentication / 401 error** — your `.env` is missing, misnamed, or the key is wrong. Recheck step 3; the variable must be exactly `GEMINI_API_KEY`.
- **Seems stuck on first run** — that's the toxicity model downloading. Let it finish; it only happens once.


## Trust-but-Verify

### Test Question 1 - Dual Agent

**1 - Query Submitted**

Ask a question: How does our employee satisfaction compare to industry standards and what policies might impact this?

Query: How does our employee satisfaction compare to industry standards and what policies might impact this?

**2 - Gemini Output**

[TOKENOMICS] Agent: manager-classifier | Input: 98 | Output: 1 | Cost: $0.000077
Route: both

[TOKENOMICS] Agent: qualitative | Input: 2228 | Output: 214 | Cost: $0.002474

✅  Qualitative answer validated.

[Qualitative]
Company documents do not establish an external industry benchmark, and any comparison with industry standards requires a separate, authoritative benchmark source [Source 1: employee_satisfacton_and_policies.txt]. Employee satisfaction may be affected by workload, manager support, career development, recognition, flexibility, and confidence in company processes, and relevant company practices include managers holding regular one-to-one meetings, teams discussing workload concerns, employees receiving feedback during the review cycle, having access to relevant training and development opportunities, following the code review process, ensuring security controls protect information without unnecessary barriers, and sharing customer complaint trends with relevant teams [Source 1: employee_satisfacton_and_policies.txt].

[TOKENOMICS] Agent: quantitative | Input: 113 | Output: 38 | Cost: $0.000227

✅  Quantitative answer validated.

[Quantitative]
Based on the company data, the average employee satisfaction score is 3.72 out of 5, paired with an average employee tenure of about 10.35 years. 

To fully answer your question:
1. Industry Standards: While our internal data provides our average satisfaction score (3.72), the provided database does not contain external benchmark data to compare this against industry standards. 
2. Impacting Policies: Similarly, the database only contains basic employee metrics and does not track specific company policies, meaning we cannot directly analyze which policies impact these satisfaction and tenure levels from this query alone.
SQL used: SELECT 
    AVG(satisfaction_score) AS average_employee_satisfaction,
    AVG(tenure_years) AS average_employee_tenure
FROM employees

**3 - Validation Layer Flags**

The validation layer presented no flags due to this query being one of the example test queries indicating the system is working correctly and all documents and SQL qeries were executed correctly. Gemini also did not produce anything out of the ordinary according to the prompt instructions. While the validation layer is very important for not outputting any hallucinations or mal-language to the user, the prompt logic and RAG system is meant to try to have Gemini output something that would pass all of those guardrails.

**4 - Accepted and Changed**

I accepted this output after carefully reviewing the SQL query use. I also accepted the guardrails the model put up which detailed the lack of information on the industry standards as this was not meant to be assumed by the model and proves the strong prompting. 

**5 - Not Trusted Output**

--------------------------------------------------------------------------------------------

### Test Question 2 - No Data

**1 - Query Submitted**

Ask a question: What is Apple's current stock price?           

Query: What is Apple's current stock price?

**2 - Gemini Output**

[TOKENOMICS] Agent: manager-classifier | Input: 91 | Output: 1 | Cost: $0.000072
Route: quantitative
/home/du_356055-1790187479/code/ga/capstones/unit-2-capstone/agents/manager.py:75: LLMOutputWarning: Invalid LLM output: SQL validation status: FAILED.
  validation = validate_quantitative(

[TOKENOMICS] Agent: quantitative | Input: 106 | Output: 22 | Cost: $0.000162

⚠️  VALIDATION WARNING: SQL validation status: FAILED

[Quantitative]
Query blocked: Read-only queries must include a FROM clause.
SQL used: SELECT 'I am unable to answer this question because stock price data is not available in the provided database schema.';

**3 - Validation Flags**

The validation layer flagged an invalid SQL query which came out as just `SELECT` due to the fact that this question was explictly prompted to test the quantitative agent with information that could not be found in the database. The first flags came out as an error message that I had orginally prompted to pop up when the SQL validation was not successful. The next warning was the validation warning showing the SQL validation status had failed. Next in the output, there was a query blocked repsonse. But finally, there was a repsonse from the review call to Gemini which properly diagnosed all the errors/warnings in the context of the question and ultimate reason for the errors which was that the stock price data was not available in the database.

**4 - Accepted and Changed**

On first review of this output, I immediately new I wanted to change at least the error message that pops up at the beginning of the answer. This makes it seem like the system is breaking but the system can actually handle this quite well as shown from the other series of outputs. The error message makes it seem like the system broke but nothing was broken, so I think this is the first manner of business before changing anything else. In regards to the output that I accepted as being the most accurate representation of the problem with the prompt, the Gemini diagnosis of the problem was the best section of the output. This accurately addresses the issue with the prompt. I also accept the validation warning as it s more broad and represents a failed SQL validation which ties into the reasoning behind why the output did not answer the question. However, I would also like to change the query blocked and SQL used statements to only be outputted when the validation layer is passed. This lead me to rediagnose my output statements to the user. I flagged a major flaw in my code at this point as I realzied my validation layers did not actually stop the out from being presented, they only flagged a warning. Thankfully, I went ahead and fixed this for both agents. For the quantitative agent, I cut off all the respnse messaging except the part I mentioned I accepted which was the LLM diagnosis that represented the issue. For the qualitative agent, I added that the response was withheld for the user protection. This was crucial to making sure my validation layer actually protected the user.

**5 - Not Trusted Output**

The output I did not trust from this was the query blocked and error statements. I knew these statements were not real errors and did not in reality have anything to do with the SQL statement at the core. The core issue was with the lack of data to support the question. I did not trust these outputs and therefore decided to resolve it by being more specific on what is outputted to the user when validation fails. This ensures that the user can trust the output they are recieving even when their answer couldn't be answered by the system. I think the user would prefer to have more integrity to their responses rather than have an answer that is not backed by the relevant context just for the sake of having an answer outputted. 

*Here is the new output after resolving these issues.*

Ask a question: What is Apple's current stock price?

Query: What is Apple's current stock price?

[TOKENOMICS] Agent: manager-classifier | Input: 91 | Output: 1 | Cost: $0.000072
Route: quantitative

[TOKENOMICS] Agent: quantitative | Input: 106 | Output: 16 | Cost: $0.000140

⚠️  VALIDATION ERROR: SQL validation status: FAILED
Error message: Error: Stock price data is not available in the provided database schema.

*Here is another example for the qualitative agent in regards to this issue.*

Query: What is the policy on PTO at the company?

[TOKENOMICS] Agent: manager-classifier | Input: 92 | Output: 2 | Cost: $0.000077
Route: qualitative

[TOKENOMICS] Agent: qualitative | Input: 2091 | Output: 65 | Cost: $0.001812

✅  Qualitative answer validated.

[Qualitative]
I cannot find this information in the provided documents.

*This output validates the answer due to the answer not c

### Test Question 3


## Tokenomics Optimisation

### Tokenomics Analysis: Qualitative vs. Quantitative Cost

The qualitative agent dominates pipeline cost. The analysis below quantifies the gap, identifies the root cause, and tests it for statistical significance.

> **Note:** Based on a small sample (2 qualitative calls, 2 quantitative calls). Treat as a strong preliminary signal, not a settled finding.

#### Per-agent comparison

| Metric | Qualitative (n=2) | Quantitative (n=2) | Qual ÷ Quant |
|---|---|---|---|
| Avg input tokens | 2,254 | 107.5 | **21.0×** |
| Avg output tokens | 231.5 | 34.0 | 6.8× |
| Avg total tokens | 2,485.5 | 141.5 | 17.6× |
| Avg cost / query | $0.002559 | $0.000208 | **12.3×** |
| Cost per 1,000 queries | $2.56 | $0.21 | 12.3× |
| Std dev of cost | $0.00012 | $0.000027 | — |
| Coefficient of variation | 4.7% | 12.9% | — |

Qualitative calls cost **~12.3× more per query (≈1,130% higher)** and do so consistently (CV of 4.7%).

#### Share of total pipeline cost

Total spend across all 7 logged calls: **$0.005757**.

| Agent | Cost | Share |
|---|---|---|
| Qualitative | $0.005118 | **88.9%** |
| Quantitative | $0.000416 | 7.2% |
| Manager-classifier | $0.000223 | 3.9% |

Nearly 9 of every 10 cents the pipeline spends goes to the qualitative agent.

#### Root cause: input context, not answer length

The gap is driven by **input tokens**, not output:

- Input tokens differ by **21×** (2,254 vs 107.5)
- Output tokens differ by only **6.8×** (231.5 vs 34)

This is the RAG signature: the qualitative agent injects ~2,200+ tokens of retrieved document context into every prompt, while the quantitative agent sends only the question plus a compact schema (~100 tokens). The retrieved context *is* the cost.

| | Cost per total token |
|---|---|
| Qualitative | ~$1.03 × 10⁻⁶ |
| Quantitative | ~$1.47 × 10⁻⁶ |

Note: quantitative is actually *more expensive per token* (higher output-token share). Qualitative wins on total cost purely because it processes **17.6× more tokens**.

#### Significance test (Welch's two-sample t-test)

Welch's test used because the group variances are unequal (~20× difference).

**Cost per query (USD):**

| Group | Call 1 | Call 2 | Mean | Sample SD |
|---|---|---|---|---|
| Qualitative | 0.002644 | 0.002474 | 0.002559 | 0.0001202 |
| Quantitative | 0.000189 | 0.000227 | 0.000208 | 0.0000269 |

**Results:**

| Statistic | Value |
|---|---|
| Mean difference | $0.002351 per query |
| t-statistic | ≈ 27.0 |
| Welch–Satterthwaite df | ≈ 1.10 |
| Two-tailed p-value | **≈ 0.024** |
| 95% CI for difference | ≈ $0.0019 – $0.0028 |

**Conclusion:** p ≈ 0.024 < 0.05 → the difference is **statistically significant**. The qualitative agent costs significantly more per query than the quantitative agent.

> A Welch's two-sample t-test found the qualitative agent's per-query cost (M = $0.00256, SD = $0.00012) significantly higher than the quantitative agent's (M = $0.00021, SD = $0.00003); *t*(1.1) ≈ 27.0, *p* ≈ 0.024. The qualitative agent cost ~12× more per query, driven by a ~21× larger input-token load from injected document context.

#### Caveats

- With n=2 per group, df ≈ 1 — the test rests on a single degree of freedom and the t-distribution's fat tails there explain why p (0.024) is far weaker than the t-statistic (27) implies.
- The effect is so large (12×, tiny within-group spread) that it clears p < 0.05 *despite* n=2 — a sign of a huge effect, not an adequate sample.
- Two queries can't capture the full range of document-context sizes; results should be confirmed with ~20–30 queries per agent.

#### Optimization takeaways

- **Trim retrieved context** (lower top-k, tighter chunk sizing) — cuts input tokens, and cost, close to linearly. Dropping ~2,250 → ~1,500 input tokens would cut qualitative cost by roughly a third.
- **Rerank, don't flood** — retrieve more candidates but pass only the top-ranked few into the prompt.
- **Don't bother optimizing the quantitative or classifier paths** — at 7.2% and 3.9% of spend, savings there are negligible. Concentrate on the qualitative path (~89% of the bill).
