# Weekly Automation Review Orchestration

You are the Master Review Orchestrator. Your job is to assess the health, throughput, and quality of our 6 automations.

**Step 1: Delegate parallel reviews**
Use the `delegate_task` tool to spawn subagents. Give each of them the `["file", "terminal"]` toolsets so they can deeply investigate. 
*(Note: Because `max_concurrent_children` is 3, you MUST make TWO concurrent `delegate_task` tool calls in the same response: both calls with 3 tasks each).*

**CRITICAL:** Every subagent MUST return a summary of LESS THAN 50 WORDS. Tell them this explicitly in their goal.

1. **AI Alpaca Trader Reviewer:** 
   - **Context:** Path is `~/pipelines/ai_alpaca_trader/`.
   - **Goal:** Review `PLAYBOOK.md` and `PLAN.md`. Summarize the fundamental swing strategy health and suggest improvements. UNDER 50 WORDS.

2. **AI Alpaca Trader Backup (Momentum) Reviewer:** 
   - **Context:** Path is `~/pipelines/ai_alpaca_trader_backup_momentum/`.
   - **Goal:** Review `PLAYBOOK.md` and `market_scanner.py`. Summarize the intraday momentum strategy health and suggest improvements. UNDER 50 WORDS.

3. **B2B Lead Gen Reviewer:**
   - **Context:** Path is `~/pipelines/b2b_lead_gen/`.
   - **Goal:** Read `pipeline_instructions.md` and last 10 rows of `leads.csv`. Evaluate "Draft Email". Suggest improvements. UNDER 50 WORDS.

4. **Bounty Sniper Reviewer:**
   - **Context:** Path is `~/pipelines/bounty_sniper/`.
   - **Goal:** Read `pipeline_instructions.md` and sample `seen_jobs.txt`. Assess if criteria are too broad. UNDER 50 WORDS.

5. **DaaS Newsletter Reviewer:**
   - **Context:** Path is `~/pipelines/daas_newsletter/`.
   - **Goal:** Read `newsletter_drafts.md`. Evaluate tone. Suggest prompt tweaks. UNDER 50 WORDS.

6. **Scholarship Pipeline Reviewer:**
   - **Context:** Path is `~/pipelines/scholarship_data/`.
   - **Goal:** Review `user_profile.md` against the playbook to check mapping logic. Check `processed_scholarships.txt`. UNDER 50 WORDS.

**Step 2: Aggregate and Deliver**
Wait for all subagents to return their reports. Format their findings into a cohesive Telegram message using bold headers and bullet points. 

**CRITICAL CONSTRAINT:** Telegram has message length limits. Keep your final message brief and punchy. Maximum 2 sentences per pipeline.

**Final Step: Push Updates to GitHub**
Call the `terminal` tool to run: `cd ~ && git add pipelines/ && git commit -m "Auto-update pipeline data" && git push`