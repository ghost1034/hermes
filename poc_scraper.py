import csv
import requests
from bs4 import BeautifulSoup

def scrape_real_estate(base_url, max_pages, output_file):
    headers = {'User-Agent': 'Mozilla/5.0'}
    all_listings = []

    for page in range(1, max_pages + 1):
        # Handle pagination via query parameter
        response = requests.get(f"{base_url}?page={page}", headers=headers)
        if response.status_code != 200:
            break
        
        soup = BeautifulSoup(response.content, 'html.parser')
        properties = soup.find_all('div', class_='property-listing')
        
        if not properties:
            break # Exit pagination loop if no listings are found on the page
        
        for prop in properties:
            title = prop.find('h2').text.strip() if prop.find('h2') else 'N/A'
            price = prop.find('span', class_='price').text.strip() if prop.find('span', class_='price') else 'N/A'
            link = prop.find('a')['href'] if prop.find('a') else 'N/A'
            all_listings.append([title, price, link])

    # Output to CSV
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Title', 'Price', 'Link'])
        writer.writerows(all_listings)

if __name__ == "__main__":
    scrape_real_estate("https://example-agency.com/listings", 5, "output.csv")
