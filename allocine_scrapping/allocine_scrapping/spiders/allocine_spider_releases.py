import scrapy
from allocine_scrapping.items import FilmItem
import datetime
import re

class AllocineSpider(scrapy.Spider):
    
    """
    This is a scrapy spider designed to scrap movies from the french website Allociné.
    """

    mois_fr_to_en = {
        'janvier': 'January', 'février': 'February', 'mars': 'March', 
        'avril': 'April', 'mai': 'May', 'juin': 'June', 
        'juillet': 'July', 'août': 'August', 'septembre': 'September', 
        'octobre': 'October', 'novembre': 'November', 'décembre': 'December'
        }
    
    def get_next_wednesday():
        today = datetime.date.today()
        # In Python's weekday convention, Monday is 0 and Sunday is 6.
        # Wednesday is represented by 2.
        wednesday = 2
        # Calculate how many days until the next Wednesday.
        days_ahead = (wednesday - today.weekday() + 7) % 7
        # If today is Wednesday, we want the next Wednesday (7 days ahead)
        if days_ahead == 0:
            days_ahead = 7
        next_wed = today + datetime.timedelta(days=days_ahead)
        return next_wed
    
    def convert_fr_date(self, date_str) -> datetime:

        """
        Convert a string formatted date into a datetime object.
        """
        for fr, en in self.mois_fr_to_en.items():
            date_str = date_str.replace(fr, en)
        
        return datetime.datetime.strptime(date_str, '%d %B %Y').date()
    
    name = "allocine_spider_releases"
    allowed_domains = ["www.allocine.fr"]
    
    #Scraps from 2010 to 2025
    start_urls = [f"https://www.allocine.fr/film/agenda/sem-{get_next_wednesday()}/"]
    
    base_url = "https://www.allocine.fr"    
    
    date = get_next_wednesday()
    
    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        """_summary_ Permet d'assigner les pipelines à cette spider

        Args:
            crawler (_type_): _description_

        Returns:
            _type_: _description_ la spider BricospiderSpider qui permet de récupérer les catégories
        """
        spider = super(AllocineSpider, cls).from_crawler(crawler, *args, **kwargs)
        # Ajouter dynamiquement une pipeline spécifique à cette spider
        crawler.settings.set('ITEM_PIPELINES', {"allocine_scrapping.pipelines.AllocineScrappingReleasesPipeline": 300})
        return spider
    
    def parse(self, response):
        
        #Loop through each film on a list page.
        films = response.css("li.mdl")
        
        for film in films:
            f = FilmItem(french_boxoffice = "", french_first_week_boxoffice = "", us_boxoffice = "", us_first_week_boxoffice = "")
            # f["picture_url"] = film.css("img.thumbnail-img::attr(src)").get()
            yield response.follow(film.css("a.meta-title-link::attr(href)").get(), callback=self.parse_film, meta={"item": f})
        
    
    def parse_film(self, film):
        
        #Instance the film Item
        f =  film.meta["item"]
        
        #Get the critics and viewer critic scores
        scores = self.get_scores(film)
        
        f["picture_url"] = film.css("figure.thumbnail img.thumbnail-img::attr(src)").get()
        
        f["title"] = film.css("div.titlebar-title.titlebar-title-xl::text").get()
        
        f['genre'] = ""
        for genre in film.css("div.meta-body-item.meta-body-info span.dark-grey-link"):
            f["genre"] += genre.css("::text").get() + '|'
        f['genre'] = f['genre'][:-1]
        
        f['actors'] = ""
        for actor in film.css("div.meta-body-item.meta-body-actor span.dark-grey-link"):
            f['actors'] += actor.css("::text").get() + '|'
        f['actors'] = f['actors'][:-1]
        
        try:
            f["date"] = film.css("div.meta-body-item.meta-body-info span.date::text").get().strip()
            # check if redif
            if self.convert_fr_date(f["date"]) < datetime.date.today():
                return
        except:
            f["date"] = "TBR"
        
        # check if there less than 5 sceances
        # _nb_sceance = film.css("div.buttons-holder span.button.button-sm.button-inverse-full span.txt::text").get().strip()
        # match = re.search(r"\((\d+)\)", _nb_sceance)
        # if match:
        #     nb = int(match.group(1))
        #     if nb < 5:
        #         return
            
        try:
            f["length"] = film.xpath('.//div[@class="meta-body-item meta-body-info"]/text()[normalize-space()]').get().strip()
        except: 
            f["length"] = "N/A"
            
        f["url"] = film.url
        
        if scores != []:
            f["critics_score"] = scores[0]
            f["viewers_score"] = scores[1]
        else:
            f["critics_score"] = "-"
            f["viewers_score"] = "-"
            
        f["synopsis"] = film.css("div.content-txt p.bo-p::text").get().strip()
        
        f["directors"] = film.css("div.meta-body-item.meta-body-direction span:nth-of-type(2)::text").get()
        
        f['vo_title'] = film.css("div.meta-body-item span.dark-grey::text").get()
        
        #Get the technical chart of a movie and get any useful info.
        tech_chart = film.css("section.section.ovw.ovw-technical div.item")
        for item in tech_chart:
            match item.css("span.what.light::text").get():
                case "Nationalités" | "Nationalité":
                    f['nationality'] = "".join(item.css("span.that span::text").getall()).strip()                   
                case "Distributeur":
                    f['editor'] = "".join(item.css("span.that::text").getall()).strip()
                case "Box Office France":
                    f['french_boxoffice'] = "".join(item.css("span.that::text").getall()).strip()
                case "Langues":
                    f['langage'] = "".join(item.css("span.that::text").getall()).strip()
                case "N° de Visa":
                    f['french_visa'] = "".join(item.css("span.that::text").getall()).strip()
                case "Année de production":
                    if f['date'] == "TBR":
                        f['date'] = "".join(item.css("span.that::text").getall()).strip()
                case _:
                    pass
        
        casting_url = self.get_casting_url(film.url)
        yield film.follow(casting_url, callback=self.parse_casting_page, meta={"item": f, "movie_url": film.url}) 
            
    def parse_casting_page(self, response):
        
        f = response.meta["item"]
        
        #If no casting page exist, return the current movie as is.
        if response.url == response.meta["movie_url"]:
            return f
        
        #Else process the page
        else:
            actors_cards = response.css("section.section.casting-actor a.meta-title-link::text").getall()
            actors_list = response.css("section.section.casting-actor a.item.link::text").getall()
            if len(actors_cards) > 0 or len(actors_list) > 0:
                f['actors'] = ""
                for actor in actors_cards:
                    f['actors'] += actor + '|'
                for actor in actors_list:
                    f['actors'] += actor + '|'
                    
                f['actors'] = f['actors'][:-1]    
                
            directors_cards = response.css("section.section.casting-director a.meta-title-link::text").getall()
            directors_list = response.css("section.section.casting-director a.item.link::text").getall()
            if len(directors_cards) > 0 or len(directors_list) > 0:
                f['directors'] = ""
                for director in directors_cards:
                    f['directors'] += director + '|'
                for director in directors_list:
                    f['directors'] += director + '|'
                    
                f['directors'] = f['directors'][:-1]   
            
        return f
    
    def get_scores(self, response):
        scores = response.css("span.stareval-note::text").getall()
        
        #Some movies can have a critic score but no viewer score.
        if scores != []:
            try:
                return [scores[0], scores[1]]
            except:
                return [scores[0], "-"]

        return []
    
    def get_casting_url(self, url):
        
        return url.replace("_gen_cfilm=", "-").replace(".html", "/casting/")

      