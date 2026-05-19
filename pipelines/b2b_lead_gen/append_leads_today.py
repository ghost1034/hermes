import csv

new_rows = [
    [
        "Moss Adams LLP", 
        "https://www.mossadams.com", 
        "careers@mossadams.com", 
        "Manual extraction of data from complex, multi-page tax documents (like K-1s) causing bottlenecks in high-volume compliance workflows.", 
        "I noticed your recent job posting for a Tax Senior in Dallas mentions utilizing GoSystem Tax RS to handle a high volume of complex partnership returns. When dealing with complex partnerships, growing teams often lose countless billable hours manually extracting and standardizing data from varied, unstructured K-1s. CPAAutomation's Universal Document Analysis can automatically extract and categorize data from any K-1 format directly for your workflow, freeing your seniors to focus on high-level review rather than manual data entry."
    ],
    [
        "Bader Martin, PS",
        "https://www.badermartin.com",
        "info@badermartin.com",
        "Managing complex compliance documents for high-net-worth clients and family offices.",
        "I saw on your Services page that your Family Office practice specializes in complex, multi-generational wealth management. Handling the large volume of unstructured financial documents for these high-net-worth clients often leads to hours of manual data entry for your staff. CPAAutomation's Universal Document Analysis can automatically extract and standardize data from varied financial statements, allowing your team to focus on strategic advisory rather than document processing."
    ],
    [
        "Jacobson Jarvis & Co, PLLC",
        "https://www.jjco.com",
        "contact@jjco.com",
        "Inefficiencies in processing grant compliance and non-profit tax forms.",
        "I noticed your firm is highly dedicated to serving the not-for-profit community, which requires meticulous tracking of grant compliance and tax reporting. Firms serving non-profits often struggle with the manual time spent auto-filling repetitive compliance documents. CPAAutomation's Form Fill technology can automatically populate standard PDFs and Word docs with your clients' data, freeing up your team to provide more proactive guidance to your non-profit partners."
    ],
    [
        "BDO USA, P.C.",
        "https://www.bdo.com",
        "careers@bdo.com",
        "Scaling audit documentation and internal communications across numerous global offices.",
        "I was reading about your recent expansion and the emphasis BDO places on continuous innovation within your audit practice. Managing documentation and ensuring consistent, high-quality reporting across so many offices can often bottleneck the review process. CPAAutomation's Inkwise offers AI-powered writing with citations that helps your teams draft and review audit communications faster and more accurately, ensuring quality while saving time."
    ],
    [
        "Grant Thornton LLP",
        "https://www.grantthornton.com",
        "info@us.gt.com",
        "Onboarding and personalized workflow configuration for new digital tools in their advisory practice.",
        "I saw your recent insights on digital transformation and how Grant Thornton is helping clients navigate complex regulatory changes. Many advisory firms face friction when trying to integrate custom AI tools into their own secure environments. CPAAutomation offers Digital Workers, like FinanceClaw, along with a personalized setup service for private agentic infrastructure, giving you a secure, custom-fit AI solution to scale your advisory capabilities."
    ]
]

domains = ["mossadams.com", "badermartin.com", "jjco.com", "bdo.com", "grantthornton.com"]

with open("/home/ianstewart/pipelines/b2b_lead_gen/leads.csv", "a", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerows(new_rows)
    
with open("/home/ianstewart/pipelines/b2b_lead_gen/processed_domains.txt", "a", encoding="utf-8") as f:
    for domain in domains:
        f.write(f"{domain}\n")
        
print("Success")