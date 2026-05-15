import csv
from urllib.parse import urlparse

new_rows = [
    [
        "Shea Labagh Dobberstein", 
        "https://www.sldcpa.com", 
        "info@sldcpa.com", 
        "Manual extraction of data from complex, unstructured client source documents into tax preparation software (ProSystem fx).", 
        "I saw on your Careers page that Shea Labagh Dobberstein is actively hiring Tax Seniors with ProSystem fx experience to support your growing San Francisco practice. Given this expansion, your senior staff are likely spending excessive billable hours manually extracting and verifying data from unstructured client source documents. Our Universal Document Analysis product can completely automate this data extraction process, seamlessly integrating with your tax software to free up your team's valuable capacity."
    ],
    [
        "SD Mayer & Associates LLP",
        "https://www.sdmayer.com",
        "info@sdmayer.com",
        "Manual data entry and processing of unstructured client documents bottlenecking their Outsourced Accounting practice.",
        "I was reviewing SD Mayer's Outsourced Accounting services and admire your team's focus on leveraging cloud technology to give Bay Area businesses real-time financial insights. As you grow this customized practice, I imagine managing the manual data entry from unstructured client documents—like diverse invoice formats and receipts—often becomes a frustrating bottleneck for your staff. Our Universal Document Analysis product automatically extracts and categorizes data from any document type, completely eliminating manual entry so your team can focus on strategic advisory work."
    ],
    [
        "Hood & Strong LLP",
        "https://www.hoodstrong.com",
        "info@hoodstrong.com",
        "Managing monthly close and document collection for numerous Client Accounting Services (CAS) clients can be tedious and require heavy manual tracking.",
        "I noticed on your website that Hood & Strong is growing its Client Accounting Services practice to support Bay Area businesses. As you take on more CAS clients, managing the monthly document collection and manual data entry across disparate systems can quickly become a bottleneck for your team. Our Universal Document Analysis product can automatically ingest, extract, and categorize data from any client document, completely streamlining your month-end processes."
    ],
    [
        "Novogradac & Company LLP",
        "https://www.novoco.com",
        "info@novoco.com",
        "Managing massive tax credit applications and real estate compliance documents.",
        "I see Novogradac is a national leader in affordable housing and tax credit services. Given the complexity and volume of compliance documents required for tax credit syndication, your team likely spends countless hours manually verifying information across hundreds of pages. Our Universal Document Analysis tool can automatically process and extract the necessary data from heavy real estate and tax credit applications, drastically reducing manual review time."
    ],
    [
        "BPM LLP",
        "https://www.bpm.com",
        "info@bpm.com",
        "Consolidating financial reporting and managing data ingestion for diverse managed services clients.",
        "I noticed BPM is actively expanding its Managed Services and Corporate Finance offerings to support a broader range of clients. Managing the continuous influx of diverse financial documents and extracting actionable insights for these clients can be incredibly labor-intensive. Our Universal Document Analysis platform can automatically ingest and structure data from any financial document, accelerating your managed services delivery and empowering your advisory team."
    ]
]

with open("/home/ianstewart/pipelines/b2b_lead_gen/leads.csv", "a", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerows(new_rows)
    
with open("/home/ianstewart/pipelines/b2b_lead_gen/processed_domains.txt", "a", encoding="utf-8") as f:
    for row in new_rows:
        url = row[1]
        domain = urlparse(url).netloc
        if domain.startswith('www.'):
            domain = domain[4:]
        f.write(f"{domain}\n")
        
print("Success")