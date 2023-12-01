import pandas as pd
import requests
from bs4 import BeautifulSoup
import csv

API_KEY = "" # Copiez votre clé d'API
horizon = "12month"

url = f"https://www.alphavantage.co/query?function=EARNINGS_CALENDAR&horizon={horizon}&apikey={API_KEY}"     #Requête query du site alphavantage

with requests.Session() as s:
    download = s.get(url)
    decoded_content = download.content.decode('utf-8')
    cr = csv.reader(decoded_content.splitlines(), delimiter=',')
    data = list(cr)


columns = data[0]                                                                                           
df = pd.DataFrame(data[1:], columns=columns)                                

df = df[~df.apply(lambda row: 'name' in row.values, axis=1)]
df = df.loc[:, ~df.columns.duplicated()]
df = df.dropna(subset=['reportDate'])
output_file_path = "calendar_data_algo.csv" # Copiez votre direction
df.to_csv(output_file_path, index=False)
