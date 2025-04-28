# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
from itemadapter import ItemAdapter
from datetime import datetime, date
import pandas as pd
import pyodbc
import requests
import os
from dotenv import load_dotenv
from twisted.internet import reactor


class AllocineScrappingPipeline:

    mois_fr_to_en = {
    'janvier': 'January', 'février': 'February', 'mars': 'March', 
    'avril': 'April', 'mai': 'May', 'juin': 'June', 
    'juillet': 'July', 'août': 'August', 'septembre': 'September', 
    'octobre': 'October', 'novembre': 'November', 'décembre': 'December'
    }
        
    def process_item(self, item, spider):
        adapter = ItemAdapter(item)

        #Change comas to points in numeric fields
        coma_to_points = ['critics_score', 'viewers_score']
        for coma in coma_to_points:
            adapter[coma] = adapter[coma].replace(",", ".")

        #Remove uncessary text and white spaces
        adapter['french_boxoffice'] = adapter['french_boxoffice'].replace(" entrées", "").replace(" ", "")
                
        #Remove white spaces
        adapter['french_first_week_boxoffice'] = adapter['french_first_week_boxoffice'].replace(" ", "")
        
        #Remove uncessary text and white spaces
        if adapter['us_boxoffice'] != "N/A":
            adapter['us_boxoffice'] = adapter['us_boxoffice'].replace(" ", "")
                
        #Remove white spaces
        if adapter["us_first_week_boxoffice"] != "N/A":
           adapter['us_first_week_boxoffice'] = adapter['us_first_week_boxoffice'].replace(" ", "")
        
        #Convert the length of the movie to minutes if availlable.
        if adapter['length'] != "N/A" and adapter['length'] != "Date de sortie inconnue":
            adapter['length'] = self.hours_to_minutes(adapter['length'])
        
        #If the release date is known, convert it to a date format.
        if adapter["date"] != "TBR" and len(adapter['date']) > 4:
            adapter['date'] = self.convert_fr_date(adapter['date'])
        
        #Transorm comas into pipes |
        adapter["langage"] = adapter["langage"].replace(", ", "|")
        
        adapter["nationality"] = adapter["nationality"].replace(" ", "|")      
        
        return item

    def close_spider(self, spider):
        """
        On the spider closing, create a parquet file from the created .csv
        """
        
        df = pd.read_csv("./allocine_spider.csv")
        df.to_parquet("allocine_spider.parquet", index=False)  
        
    
    def hours_to_minutes(self, h)  -> int:
        """
        Transform string formatted movie length into minutes.
        """
        
        split = h.split()
        hours = split[0].split("h")[0]
        hours = int(hours)*60
        minutes = split[1].split("min")[0]
        
        return int(hours) + int(minutes)

    def convert_fr_date(self, date_str) -> datetime:

        """
        Convert a string formatted date into a datetime object.
        """
        
        for fr, en in self.mois_fr_to_en.items():
            date_str = date_str.replace(fr, en)
        
        return datetime.strptime(date_str, '%d %B %Y').date()

        
# region RELEASES

class AllocineScrappingReleasesPipeline:

    mois_fr_to_en = {
    'janvier': 'January', 'février': 'February', 'mars': 'March', 
    'avril': 'April', 'mai': 'May', 'juin': 'June', 
    'juillet': 'July', 'août': 'August', 'septembre': 'September', 
    'octobre': 'October', 'novembre': 'November', 'décembre': 'December'
    }

    def open_spider(self, spider):
        
        load_dotenv()
        
        self.conn = pyodbc.connect(
             'DRIVER={ODBC Driver 18 for SQL Server};'
            f'SERVER={os.getenv("DB_HOST")};'
            f'DATABASE={os.getenv("DB_NAME")};'
            f'UID={os.getenv("DB_USER")};'
            f'PWD={os.getenv("DB_PASSWORD")}'            
        )
        self.cursor = self.conn.cursor()
        
    def process_item(self, item, spider):
        adapter = ItemAdapter(item)

        #Change comas to points in numeric fields
        coma_to_points = ['critics_score', 'viewers_score']
        for coma in coma_to_points:
            adapter[coma] = adapter[coma].replace(",", ".")

        #Remove uncessary text and white spaces
        adapter['french_boxoffice'] = adapter['french_boxoffice'].replace(" entrées", "").replace(" ", "")
                
        #Remove white spaces
        adapter['french_first_week_boxoffice'] = adapter['french_first_week_boxoffice'].replace(" ", "")
        
        #Remove uncessary text and white spaces
        if adapter['us_boxoffice'] != "N/A":
            adapter['us_boxoffice'] = adapter['us_boxoffice'].replace(" ", "")
                
        #Remove white spaces
        if adapter["us_first_week_boxoffice"] != "N/A":
           adapter['us_first_week_boxoffice'] = adapter['us_first_week_boxoffice'].replace(" ", "")
        
        #Convert the length of the movie to minutes if availlable.
        if adapter['length'] != "N/A" and adapter['length'] != "Date de sortie inconnue":
            adapter['length'] = self.hours_to_minutes(adapter['length'])
        
        #If the release date is known, convert it to a date format.
        adapter['date'] = spider.date
        
        #Transorm comas into pipes |
        adapter["langage"] = adapter["langage"].replace(", ", "|")
        
        adapter["nationality"] = adapter["nationality"].replace(" ", "|")      
        
        return item

    def close_spider(self, spider):
        
        reactor.callLater(0, self.process_csv)
    
    def process_csv(self):
        df = pd.read_csv(f"./allocine_spider_releases_{str(date.today())}.csv")
        
        print(df["title"], df.shape)
        
        df['genre'] = df['genre'].str.split('|')
        df['actors'] = df['actors'].str.split('|')
        df['actors'] = df['actors'].mask(df['actors'].isna(), ['no value'])
        df['directors'] = df['directors'].mask(df['directors'].isna(), ['no value'])
        df['nationality'] = df['nationality'].str.split('|')
        df['langage'] = df['langage'].str.split('|')     
        df['directors'] = df['directors'].str.split('|')     
        df['date']= pd.to_datetime(df['date'], errors='coerce')
        df["date"] = df["date"].dt.strftime("%Y-%m-%dT%H:%M:%S")
        df2  = df[["actors", "date", "directors", "editor", "genre", "langage", "length", "nationality", "title"]]
        movies = []
        movies_items = []
        for (index, row), (index2, row2) in zip(df2.iterrows(), df.iterrows()):
            if row["actors"] == "no value":
                row["actors"] = []
            if row["directors"] == "no value":
                row["directors"] = []
                
            movies.append(row.to_dict())
            movies_items.append({"title": row2["title"], "url": row2['url'], 'picture_url': row2['picture_url'],\
                'synopsis': row2['synopsis'], 'date': row2['date'], 'predicted_affluence': 0})
        
        response = requests.post(os.getenv("API_URL"),json=movies)
        predictions = response.json()
       
        predictions = sorted(predictions["predictions"], key=lambda x: x["predicted_affluence"], reverse=True)
        for prediction in predictions:
            if prediction["predicted_affluence"] < 0:                
                prediction["predicted_affluence"] = 0      
            else:
                prediction["predicted_affluence"] = int(prediction["predicted_affluence"]/2000)
            
            if prediction["second_predicted_affluence"] < 0:                
                prediction["second_predicted_affluence"] = 0      
            else:
                prediction["second_predicted_affluence"] = int(prediction["second_predicted_affluence"]/2000)
                
            for movie_item in movies_items:
                if movie_item['title'] == prediction["title"]:
                    movie_item['predicted_affluence'] = prediction["predicted_affluence"] 
                    movie_item['predicted_affluence_2'] = prediction["second_predicted_affluence"]  
                    movie_item['shap_values'] = prediction['shap_values']
                    movie_item['shap_values_2'] = prediction['second_shap_values']
                    break
            
        for movie_item in movies_items:
            self.insert_item(movie_item)  
        
        self.conn.commit()
        self.conn.close()
        os.remove(f"./allocine_spider_releases_{str(date.today())}.csv")
    
    def insert_item(self, item):
        
        self.cursor.execute(
            """
            INSERT INTO app_movie (title, url, picture_url, synopsis, date, real_affluence, predicted_affluence, predicted_affluence_2, shap_values, shap_values_2)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            item['title'],
            item['url'],
            item['picture_url'],
            item['synopsis'],
            item["date"],
            0,
            item['predicted_affluence'],
            item['predicted_affluence_2'],
            item['shap_values'],
            item['shap_values_2']
        )
    
        
    def hours_to_minutes(self, h)  -> int:
        """
        Transform string formatted movie length into minutes.
        """
        
        split = h.split()
        hours = split[0].split("h")[0]
        hours = int(hours)*60
        minutes = split[1].split("min")[0]
        
        return int(hours) + int(minutes)

    def convert_fr_date(self, date_str) -> datetime:

        """
        Convert a string formatted date into a datetime object.
        """
        
        for fr, en in self.mois_fr_to_en.items():
            date_str = date_str.replace(fr, en)
        
        return datetime.strptime(date_str, '%d %B %Y').date()