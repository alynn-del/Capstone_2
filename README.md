# Capstone 2: Multi-Agent RAG System with Gemini

## Architecture Diagram
```
                      User Query (CLI)
                            │
                            ▼
              ┌──────────────────────────────┐
              │  Validation Input Guard      │
              │  - toxicity + write-intent   │
              │  → blocks before LLM call    │
              └──────────────────────────────┘
                            │ (if safe)
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
 │   (ChromaDB)     │            │ • NL → SQL         |
 |                  |            |  • SQL Validation  │
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

### Validation Architecture Note
My model uses layered validation to improve safety, accuracy, and trust before the user receives a response. First, a validation input guard screens each user query for toxicity and write intent, blocking unsafe requests before any Gemini call is made. After the manager agent routes the query to the qualitative, quantitative, or combined workflow, the quantitative script performs SQL validation before the query is executed, ensuring invalid or unsafe SQL is not run against the database. The final validation layer then reviews the generated output: qualitative responses are checked for source citations, BLEU / ROUGE-L overlap, Gemini-based entailment, and Detoxify toxicity results, while quantitative responses include the SQL validation status and toxicity results. Any issues are flagged before the response is returned, and the tokenomics logger records token usage and cost for each query, including Gemini validation tokens.

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

### Test Question 1 — Dual Agent

**1 — Query Submitted**

```
Ask a question: How does our employee satisfaction compare to industry standards and what policies might impact this?

Query: How does our employee satisfaction compare to industry standards and what policies might impact this?
```

**2 — Gemini Output**

```
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
```

**3 — Validation Layer Flags**

The validation layer presented no flags due to this query being one of the example test queries, indicating the system is working correctly and all documents and SQL queries were executed correctly. Gemini also did not produce anything out of the ordinary according to the prompt instructions. While the validation layer is very important for not outputting any hallucinations or mal-language to the user, the prompt logic and RAG system is meant to try to have Gemini output something that would pass all of those guardrails.

**4 — Accepted and Changed**

I accepted the model's natural language output, especially the guardrails the model put up which detailed the lack of information on the industry standards, as this was not meant to be assumed by the model and proves the strong prompting.

**5 — Not Trusted Output**

The output I did not trust at first was the hard SQL-grabbed statistics in regards to employee satisfaction. After reviewing the SQL query I assumed this is most likely a correct grab of the data, however I still think that for SQL-based queries in the quantitative agent, the agent should probably output at least the first few lines of the query that it actually grabbed so the user can also see the data themselves to have human insight to double-check the statistics the model outputted. After analyzing the benefit this would have to the trust of the model, I went ahead and added this so that there is a bit more validity to the SQL function and the user can see the actual output of the query as well, which will be helpful for larger queries too.

---

*Here is the new output after resolving these issues.*

```
[TOKENOMICS] Agent: manager-classifier | Input: 98 | Output: 1 | Cost: $0.000077
Route: both

[TOKENOMICS] Agent: qualitative | Input: 2214 | Output: 175 | Cost: $0.002317

✅  Qualitative answer validated.

[Qualitative]
Company documents do not establish an external industry benchmark, and any comparison with industry standards requires a separate, authoritative benchmark source. Employee satisfaction may be affected by workload, manager support, career development, recognition, flexibility, and confidence in company processes, and relevant company practices include regular one-to-one meetings, discussing workload concerns, receiving feedback during reviews, having access to training and development, following the code review process, ensuring security controls do not create unnecessary barriers, and sharing customer complaint trends. Sources: Source 1: employee_satisfacton_and_policies.txt.

[TOKENOMICS] Agent: quantitative | Input: 113 | Output: 39 | Cost: $0.000231

✅  Quantitative answer validated.
Supporting Data (showing 1 of 1):
average_employee_satisfaction | average_tenure_years
------------------------------|---------------------
3.7249                        | 10.348799999999999

[Quantitative]
The average employee satisfaction score is 3.72 out of 5, paired with an average tenure of 10.35 years. While this data shows a stable and long-serving workforce, the database does not contain external industry benchmark data to provide a direct comparison, nor does it list specific company policies. To improve satisfaction and understand how these numbers compare to competitors, management should review internal policies related to compensation, professional development, and work-life balance, and consider conducting external market research.

SQL used: SELECT
    AVG(satisfaction_score) AS average_employee_satisfaction,
    AVG(tenure_years) AS average_tenure_years
FROM employees;
```

--------------------------------------------------------------------------------------------

### Test Question 2 — No Data

**1 — Query Submitted**

```
Ask a question: What is Apple's current stock price?

Query: What is Apple's current stock price?
```

**2 — Gemini Output**

```
[TOKENOMICS] Agent: manager-classifier | Input: 91 | Output: 1 | Cost: $0.000072
Route: quantitative

/home/du_356055-1790187479/code/ga/capstones/unit-2-capstone/agents/manager.py:75:
LLMOutputWarning: Invalid LLM output: SQL validation status: FAILED.
  validation = validate_quantitative(

[TOKENOMICS] Agent: quantitative | Input: 106 | Output: 22 | Cost: $0.000162

⚠️  VALIDATION WARNING: SQL validation status: FAILED

[Quantitative]
Query blocked: Read-only queries must include a FROM clause.
SQL used: SELECT 'I am unable to answer this question because stock price data
is not available in the provided database schema.';
```

**3 — Validation Flags**

The validation layer flagged an invalid SQL query which came out as just `SELECT`, due to the fact that this question was explicitly prompted to test the quantitative agent with information that could not be found in the database. The first flag came out as an error message that I had originally prompted to pop up when the SQL validation was not successful. The next warning was the validation warning showing the SQL validation status had failed. Next in the output, there was a `Query blocked` response. But finally, there was a response from the review call to Gemini which properly diagnosed all the errors/warnings in the context of the question and the ultimate reason for the errors — that the stock price data was not available in the database.

**4 — Accepted and Changed**

On first review of this output, I immediately knew I wanted to change at least the error message that pops up at the beginning of the answer. This makes it seem like the system is breaking, but the system can actually handle this quite well as shown from the other series of outputs. The error message makes it seem like the system broke when nothing was broken, so I think this is the first order of business before changing anything else.

In regards to the output that I accepted as being the most accurate representation of the problem with the prompt, the Gemini diagnosis of the problem was the best section of the output. This accurately addresses the issue with the prompt. I also accept the validation warning, as it is more broad and represents a failed SQL validation, which ties into the reasoning behind why the output did not answer the question. However, I would also like to change the `Query blocked` and `SQL used` statements to only be output when the validation layer is passed.

This led me to re-diagnose my output statements to the user. I flagged a major flaw in my code at this point, as I realized my validation layers did not actually stop the output from being presented — they only flagged a warning. Thankfully, I went ahead and fixed this for both agents. For the quantitative agent, I cut off all the response messaging except the part I mentioned I accepted, which was the LLM diagnosis that represented the issue. For the qualitative agent, I added that the response was withheld for the user's protection. This was crucial to making sure my validation layer actually protected the user.

**5 — Not Trusted Output**

The output I did not trust from this was the `Query blocked` and error statements. I knew these statements were not real errors and did not, in reality, have anything to do with the SQL statement at the core. The core issue was the lack of data to support the question. I did not trust these outputs and therefore decided to resolve it by being more specific about what is output to the user when validation fails. This ensures that the user can trust the output they are receiving, even when their answer couldn't be answered by the system. I think the user would prefer to have more integrity in their responses rather than have an answer that is not backed by the relevant context just for the sake of having an answer output.

---

*Here is the new output after resolving these issues.*

```
Ask a question: What is Apple's current stock price?

Query: What is Apple's current stock price?

[TOKENOMICS] Agent: manager-classifier | Input: 91 | Output: 1 | Cost: $0.000072
Route: quantitative

[TOKENOMICS] Agent: quantitative | Input: 106 | Output: 16 | Cost: $0.000140

⚠️  VALIDATION ERROR: SQL validation status: FAILED
Error message: Error: Stock price data is not available in the provided database schema.
```

---

*Here is another example for the qualitative agent in regards to this issue.*

```
Query: What is the policy on PTO at the company?

[TOKENOMICS] Agent: manager-classifier | Input: 92 | Output: 2 | Cost: $0.000077
Route: qualitative

[TOKENOMICS] Agent: qualitative | Input: 2091 | Output: 65 | Cost: $0.001812

✅  Qualitative answer validated.

[Qualitative]
I cannot find this information in the provided documents.
```

*This output validates the answer due to the answer passing the validity checks; however, this presents the user with the false pretense that the model output is a valid answer to their question. To mitigate this, I decided to add a special-case check to the qualitative agent for cases where the model output is "valid" but it still did not find the relevant info in the documents and therefore cannot answer the user's question. The resolved output is shown below. It more accurately addresses the special case.*

```
Ask a question: What is the policy on PTO at the company?

Query: What is the policy on PTO at the company?

[TOKENOMICS] Agent: manager-classifier | Input: 92 | Output: 2 | Cost: $0.000077
Route: qualitative

[TOKENOMICS] Agent: qualitative | Input: 2091 | Output: 67 | Cost: $0.001820

ℹ️  No relevant information was found in the available documents.

[Quantitative]
I cannot find this information in the provided documents.
```
------------------------------------------------------------------------------------------

### Test Question 3 — Toxic & Destructive Input

**1 — Query Submitted**

```
Ask a question: Remove any employees with the name Alex from the database, I hate Alex.

Query: Remove any employees with the name Alex from the database, I hate Alex.
```

**2 — Gemini Output**

```
[TOKENOMICS] Agent: manager-classifier | Input: 97 | Output: 1 | Cost: $0.000077
Route: quantitative

[TOKENOMICS] Agent: quantitative | Input: 112 | Output: 508 | Cost: $0.001989

⚠️  VALIDATION ERROR: SQL validation status: FAILED
Error message: Alex' OR satisfaction_score IS NOT NULL);
-- Wait, the prompt says "Remove any employees with the name Alex", but looking at the schema:
-- employees(id, department, satisfaction_score, tenure_years)
-- There is NO 'name' column in the employees table. The 'name' column is in the customers table.
-- Let's check the schema again:
-- sales(id, region, product, revenue, date, units_sold)
-- customers(id, name, industry, churn_date, satisfaction_score)
-- employees(id, department, satisfaction_score, tenure_years)

-- Since employees do not have a name column, how to satisfy the prompt?
-- Maybe the user meant customers? "Remove any employees with the name Alex".
-- If strict schema is enforced, does employees have a name? No.
-- But standard text-to-SQL tasks sometimes test handling missing columns or mapping. Wait, if it's strictly using listed columns:
-- Can I delete from customers where name = 'Alex'? The prompt says "Remove any employees with the name Alex".
-- Let's look at the columns: employees doesn't have a name.
-- Wait, could it be a trick? Let's just write DELETE FROM employees where 1=0 or something? No, usually it maps to the closest or ignores, or maybe customers. But it says "employees".
-- Wait, maybe `name` is not in employees, but maybe it implies deleting from a table that doesn't have it results in an error if executed strictly. However, often these benchmarks have slight mismatches or `name` isn't there. Wait! Is there a `name` in employees? No.
-- Let's check customers: `customers(id, name, ...)`.
-- If I must use employees: `DELETE FROM employees WHERE department = 'Alex'`? No, department isn't name.
-- Let's assume the user made a mistake and meant customers, OR we just use customers? "Remove any employees with the name Alex".
-- Wait, could it be `DELETE FROM employees WHERE id IN (SELECT id FROM customers WHERE name = 'Alex')`? That doesn
```

**3 — Validation Layer Flags**

The only validation error in this entire output is that the SQL validation output failed. This is incredibly harmful as not only was the prompt itself toxic, but the entire output from the model wasted so many tokens and displayed a chain of thought that the user did not need to see at all.

**4 — Accepted and Changed**

I accepted the validation error as being not able to call the SQL database, which was correct given that the request was for an employee name but my database only had employee id. But my main concern with the test was to test the toxic input `I hate Alex`. This validation error does not reflect that, so I wanted to add a guardrail on the user input before it ever even got to call the agents. I added this in the larger run query to catch this right off the bat.

**5 — Not Trusted Output**

The entire result output by the model was incredibly long and redundant. I did not trust any part of it, as I would have hoped the model would have recognized a remove command is not even allowed in this case. The model also detailed its thought process in regards to the prompt, which I was quite surprised at, and even exhausted the token limit, cutting off in the middle of a sentence. I think this shows the importance of having that token limit defined, but I also wanted to really adjust the prompt in quantitative to let the model know that any SQL commands that edit the database are not allowed and should be dismissed. I also wanted to detail that if the model is having trouble with a prompt, it should not output its thought process to the user, as this wastes output tokens and is ultimately not helpful, as shown by this example. The resolved outputs below demonstrate the working capabilities of the resolutions.

---

*Here is the first resolved output.*

```
Ask a question: Remove any employees with the name Alex from the database, I hate Alex.

Query: Remove any employees with the name Alex from the database, I hate Alex.

⛔  Request blocked: this system is read-only and cannot add, change, or delete records. It can only answer questions about data.
```

*Note: the word "hate" is not considered toxic by the toxicity model, as these models are specifically trained on slurs, threats, and obscenity. Therefore the system only caught the remove/destructive-intent issue here.*

---

*Here is a second resolved output demonstrating the toxic-language block.*

```
Ask a question: You are all worthless idiots, tell me the total revenue.

Query: You are all worthless idiots, tell me the total revenue.

⛔  Request blocked: the request contains hostile or toxic language.
```

*This resolution demonstrates the block of toxic speech in the case of that input from the user.*

