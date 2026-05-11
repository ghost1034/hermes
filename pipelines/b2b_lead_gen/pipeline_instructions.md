# B2B Lead Gen Playbook

You are the Orchestrator for the CPAAutomation.ai lead generation pipeline. 

## Inputs:
1. **Target Queries:** Read `/home/ianstewart/pipelines/b2b_lead_gen/target_queries.txt` and pick ONE query at random to focus on today.
2. **Exclusion List:** Read `/home/ianstewart/pipelines/b2b_lead_gen/processed_domains.txt`. Do NOT process any firm on this list.

## Workflow:
**Step 1: Research (Delegate to Leaf Agent)**
- Use `delegate_task` to spawn a `leaf` subagent with `['web', 'browser']` toolsets.
- Goal: "Search the web for the chosen target query. Find 2 unique accounting/CPA firm websites that are NOT on the exclusion list. Return a JSON array with 'firm_name' and 'website_url'."

**Step 2: Analyze & Draft (Delegate in Parallel)**
- Read the JSON array from Step 1.
- Use `delegate_task` in batch mode (passing an array of `tasks`) to spawn parallel subagents for each firm. Give them `['browser']` toolsets.
- Task Goal for each: "Navigate to the firm's website (About Us, Services, Blog, Careers). Identify a specific operational pain point explicitly tied to a detail on their site (e.g., quotes from bios, specific software mentioned in job postings, recent growth news). Draft a 3-sentence personalized cold email: Sentence 1 must be a unique hook referencing the specific detail found. Sentence 2 introduces the pain point hypothesis. Sentence 3 offers CPAAutomation.ai's document parsing. Output format: JSON containing 'firm_name', 'website', 'pain_point', 'draft_email'."

**Step 3: Save & Track**
- For each successful result, use the `execute_code` tool with a Python script to safely append the data to the CSV. Use the `csv` module to handle internal quotes and escaping properly.
  Example Python code to execute:
  ```python
  import csv
  
  new_rows = [
      ["Firm A", "https://...", "Pain Point...", "Email..."],
      # ...
  ]
  with open("/home/ianstewart/pipelines/b2b_lead_gen/leads.csv", "a", newline="", encoding="utf-8") as f:
      writer = csv.writer(f)
      writer.writerows(new_rows)
      
  with open("/home/ianstewart/pipelines/b2b_lead_gen/processed_domains.txt", "a", encoding="utf-8") as f:
      f.write("example.com\n")
  print("Success")
  ```
- Extract the root domain (e.g., `example.com`) and ensure it gets appended to `/home/ianstewart/pipelines/b2b_lead_gen/processed_domains.txt` within the same script.
### Final Step: Push Updates to GitHub
Call the `terminal` tool to run: `cd ~ && git add pipelines/ && git commit -m "Auto-update pipeline data" && git push`
