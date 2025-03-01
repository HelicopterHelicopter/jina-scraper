import requests
import xml.etree.ElementTree as ET
import urllib.parse
import json
from openai import OpenAI
import os
from dotenv import load_dotenv
import pymongo
import certifi
from google.oauth2 import service_account
import vertexai
from vertexai.generative_models import GenerativeModel
import re

my_credentials = service_account.Credentials.from_service_account_file(
    'credentials.json'
)

vertexai.init(project="ds-gemini-423306", location="us-central1", credentials = my_credentials)

model = GenerativeModel(
    "gemini-2.0-flash",
    generation_config = {
    "temperature": 0.5,
    #"top_k":1
    "top_p": 0.95,
}
)



load_dotenv()

mongo_client = pymongo.MongoClient(os.getenv("MONGO_URI"),tlsCAFile=certifi.where())

db = mongo_client["remus"]

site_data_collection = db["site_data"]

# llm_client =OpenAI(
#     base_url="https://integrate.api.nvidia.com/v1",
#     api_key= os.getenv("nim_api_key")
# )

# model = "meta/llama-3.3-70b-instruct"

def get_site_maps(url):
    site_map_url = url + '/sitemap.xml'
    response = requests.get(site_map_url)
    return response.text

def convert_site_map_to_array(site_map_data):
    try:
        root = ET.fromstring(site_map_data)
        urls = []
        namespace = ''
        if '}' in root.tag:
            namespace = root.tag.split('}')[0] + '}'
        print(root)
        for url_elem in root.findall(f".//{namespace}url"):
            print(url_elem)
            loc_elem = url_elem.find(f"{namespace}loc")
            if loc_elem is not None:
                urls.append(loc_elem.text.strip())

        return urls
    except Exception as e:
        print('Error parsing XML: ', e)
        return []
    
def get_markdown_from_url(url):
    jina_url = 'https://r.jina.ai/' + urllib.parse.quote(url)
    response = requests.get(jina_url)
    return response.text

def clean_json_output(response):
    return re.sub(r"```json(.*?)```", r"\1", response, flags=re.DOTALL).strip()

def main():
    url = 'https://www.thesouledstore.com'
    site_maps_xml = get_site_maps(url)
    site_maps = convert_site_map_to_array(site_maps_xml)

    base_prompt = "You will be given a markdown file data which was scraped from a website. Find all the important data from the markdown such as information about the company, products, product images, pricing, offers, etc. You group all the related information together and structure it in JSON format. Try to group the images with their respective products. The image urls start with https://prod-img.thesouledstore.com. If they dont start with that URL do not hallucinate and keep the image url empty for that product. You can also add any additional information that you think is important and can be advertised. Navigation links are not needed. Print only the json, no extra text. Do not format JSON responses inside code blocks. Instead, return them as plain text . \n\n"

    for site_map in site_maps:
        site_map_data = get_markdown_from_url(site_map)
        print(site_map_data)

        response_string = model.generate_content(base_prompt + site_map_data)

        print(response_string.text)

        json_data = json.loads(clean_json_output(response_string.text))

        print(json_data)

        site_data_collection.insert_one({
            "url": site_map,
            "data": json_data
        })

if __name__ == "__main__":
    main()
