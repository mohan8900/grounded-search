# Combined Google APIs + Gemini Flash 2.5 Business Search Engine (Flask Backend)
import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import google.generativeai as genai

app = Flask(__name__)
CORS(app)
API_KEY = os.getenv("AIzaSyDyXtvUClHo5GL3S8WAJN3tIGOYwEGZ120")
CX = os.getenv("0239e658732fc4240")
GEMINI_API_KEY = os.getenv("AIzaSyDyXtvUClHo5GL3S8WAJN3tIGOYwEGZ120")

# Configure Gemini Flash
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

@app.route('/search', methods=['POST'])
def search():
    query = request.json.get("query", "").strip()

    # Expand Known Acronyms
    known_acronyms = {
        "tcs": "Tata Consultancy Services",
        "cts": "Cognizant Technology Solutions",
        "ibm": "IBM Corporation",
        "wipro": "Wipro Limited",
        "hcl": "HCL Technologies"
    }
    query_lower = query.lower()
    if query_lower in known_acronyms:
        query = known_acronyms[query_lower]

    # Knowledge Graph
    kg_url = "https://kgsearch.googleapis.com/v1/entities:search"
    kg_params = {"query": query, "key": API_KEY, "limit": 1}
    kg_items = requests.get(kg_url, params=kg_params).json().get("itemListElement", [])
    knowledge_card = kg_items[0]["result"] if kg_items else {}

    # Google Custom Search with optional site restriction
    site_url = knowledge_card.get("url")
    google_url = "https://www.googleapis.com/customsearch/v1"
    google_params = {
        "q": query,
        "key": API_KEY,
        "cx": CX,
    }
    if site_url:
        domain = site_url.replace("https://", "").replace("http://", "").split("/")[0]
        google_params["siteSearch"] = domain
        google_params["siteSearchFilter"] = "i"

    google_results = requests.get(google_url, params=google_params).json().get("items", [])

    # Prompt Gemini Flash
    google_snippets = "\n".join([f"- {item.get('title', '')}: {item.get('link', '')}" for item in google_results])

    context = f"""
    Company Query: {query}

    \U0001f517 Google Search Results:
    {google_snippets}

    \U0001f4da Knowledge Card:
    Name: {knowledge_card.get('name', 'N/A')}
    Description: {knowledge_card.get('description', 'N/A')}

    Please generate a clean, Knowledge Card-style summary using bullet points or label-value format, like:
    Name: Example Corp
    Founded: 1995
    Headquarters: New York, NY
    Description: A leading technology services company.
    """

    try:
        gemini_response = model.generate_content(context)
        gemini_summary = gemini_response.text
    except Exception as e:
        gemini_summary = f"(Gemini error) {str(e)}"

    official_url = knowledge_card.get('url', site_url) or site_url

    # Extract and prioritize 3rd-party links
    known_sources = ["linkedin.com", "facebook.com", "twitter.com", "instagram.com",
                     "crunchbase.com", "glassdoor.com", "yelp.com", "indeed.com"]

    third_party_urls = []
    for item in google_results:
        url = item.get("link", "")
        if any(source in url for source in known_sources):
            third_party_urls.append(url)

    # Deduplicate and limit to 8 best links
    third_party_urls = list(dict.fromkeys(third_party_urls))[:8]

    return jsonify({
        "official_url": official_url,
        "query": query,
        "knowledge_card": knowledge_card,
        "summary": gemini_summary,
        "third_party_urls": third_party_urls
    })

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)
