import os
import re
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin


def load_10k_xbrl(cik_num):
    if not cik_num:
        print("CIK number is required.")
        return []

    url_to_all_10k = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik_num}&type=10-K&dateb=&owner=include&count=100&search_text="

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
    }

    try:
        response = requests.get(url_to_all_10k, headers=headers)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')
        table = soup.find('table', class_='tableFile2')

        if not table:
            print(f"No table found for CIK {cik_num}.")
            return []

        full_links = []
        for row in table.find_all('tr')[1:]:  # Skip header row
            cols = row.find_all('td')
            if len(cols) > 3 and cols[0].text.strip() == '10-K':
                doc_link = cols[1].find('a', href=True)['href']
                full_links.append(f"https://www.sec.gov{doc_link}")

        return full_links

    except requests.RequestException as e:
        print(f"Network error while fetching 10-K filings for CIK {cik_num}: {e}")
        return []


def get_xbrl_links(link):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
    }

    try:
        response = requests.get(link, headers=headers)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')
        file_links = []
        folder_name = None

        for a_tag in soup.find_all('a', href=True):
            file_link = urljoin(link, a_tag['href'])
            # change to for other file type
            if file_link.endswith('.xml'):
                folder_name_new = re.split(r'[._]', file_link.split('/')[-1])[0]
                folder_name = folder_name or folder_name_new
                file_links.append(file_link)

        return file_links, folder_name

    except requests.RequestException as e:
        print(f"Network error while accessing link {link}: {e}")
        return [], None


def download_file(session, file_link, folder_path):
    file_name = os.path.basename(file_link)
    file_path = os.path.join(folder_path, file_name)

    for attempt in range(3):
        try:
            response = session.get(file_link)
            response.raise_for_status()
            with open(file_path, 'wb') as file:
                file.write(response.content)
            print(f"Downloaded: {file_path}")
            return file_path
        except requests.RequestException as e:
            print(f"Failed to download {file_link} (Attempt {attempt + 1}): {e}")

    return None


def download_sec_files(link, download_dir):
    file_links, folder_name = get_xbrl_links(link)
    if not file_links:
        print(f"No files found for link: {link}")
        return folder_name, None

    folder_path = os.path.join(download_dir, folder_name)
    os.makedirs(folder_path, exist_ok=True)

    xbrl_name = None
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
    })

    for file_link in file_links:
        downloaded_file = download_file(session, file_link, folder_path)
        if downloaded_file and '_htm.xml' in downloaded_file:
            xbrl_name = downloaded_file

    return folder_name, xbrl_name


# Main process
try:
    # Load CIKs from JSON file
    with open('test.json', 'r') as file:
        cik_list = json.load(file)

    # Iterate over companies and process their filings
    parent_dir = "./downloads"  # Adjust the directory as needed
    os.makedirs(parent_dir, exist_ok=True)

    for company in cik_list:
        cik_number = company['CIK'].strip()
        company_name = company['company_name'].strip()

        print(f"Processing {company_name} (CIK: {cik_number})...")

        urls = load_10k_xbrl(cik_number)
        if not urls:
            print(f"No 10-K filings found for {company_name} (CIK: {cik_number}).")
            continue

        download_dir = os.path.join(parent_dir, f"{cik_number} - {company_name}")
        os.makedirs(download_dir, exist_ok=True)

        for url in urls:
            folder, xbrl_file = download_sec_files(url, download_dir)
            print(f"Downloaded to folder: {folder}, Main XBRL File: {xbrl_file}")

except FileNotFoundError as e:
    print(f"File not found: {e}")
except json.JSONDecodeError as e:
    print(f"Error decoding JSON: {e}")
except Exception as e:
    print(f"An unexpected error occurred: {e}")
