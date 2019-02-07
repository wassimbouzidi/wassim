import flask
from flask import request, jsonify
from typing import Tuple
import csv
from collections import defaultdict
import geopy.distance
from operator import itemgetter

application = flask.Flask(__name__)
application.config["DEBUG"] = True

def distance(first_latitude, first_longitude, second_latitude, second_longitude):
   coords_1 = (first_latitude, first_longitude)
   coords_2 = (second_latitude, second_longitude)
   return geopy.distance.vincenty(coords_1, coords_2).km
 
def getScoreOfDist(partial_score, distance):
   if distance < 250:
      return partial_score
   elif distance < 500:
      return partial_score * 3 / 4
   elif distance < 1000:
      return partial_score / 2
   elif distance < 2500:
      return partial_score / 4
   else:
	   return 0
def getScoreOfPop(partial_score, city_pop):
   if city_pop > 1000000:
      return partial_score
   elif city_pop > 100000:
      return partial_score * 3 / 4
   elif city_pop > 50000:
      return partial_score / 2
   elif city_pop > 10000:
      return partial_score / 4
   else:
      return 0
def getScoreOfNameVsPrefix(partial_score, name, prefix):
   if name == prefix:
      return partial_score
   elif len(name) - len(prefix) == 1:
      return partial_score * 3 / 4
   elif len(name) - len(prefix) == 2:
      return partial_score / 2
   elif len(name) - len(prefix) == 3:
      return partial_score / 4
   else:
      return 0

class City(object):
   def __init__(self, name, latitude, longitude, population):
      self.name = name
      self.latitude = latitude
      self.longitude = longitude
      self.score = 0
      self.population = population
   def __dict__(self):
    d = {
    'city_name' : self.name,
    'latitude' : self.latitude,
	'longitude' : self.longitude,
    'score' : self.score
    }
    return d
   def __score__(self, nb_occ, latitude, longitude, prefix):
      if nb_occ == 1:
         self.score = 1
      else:
         if nb_occ >= 10:
            first_score = 0.1
         else:
            first_score = 1 / nb_occ 
         self.score = first_score
         if latitude is not None:		 
            self.score += getScoreOfDist((1-first_score)/3, distance(latitude, longitude, self.latitude, self.longitude))
            self.score += getScoreOfPop((1-first_score)/3, self.population)
            self.score += getScoreOfNameVsPrefix((1-first_score)/3, self.name, prefix)
         else:
            self.score += getScoreOfPop((1-first_score)/2, self.population)
            self.score += getScoreOfNameVsPrefix((1-first_score)/2, self.name, prefix)
         self.score = round(self.score, 1)
         
class TrieNode:
    def __init__(self):
        self.end = False
        self.children = {}

    def all_words(self, prefix):
        if self.end:
            yield prefix

        for letter, child in self.children.items():
            yield from child.all_words(prefix + letter)
			
			
			
class Trie:
   def __init__(self):
        self.root = TrieNode()

   def insert(self, word):
        curr = self.root
        for letter in word:
            node = curr.children.get(letter)
            if not node:
                node = TrieNode()
                curr.children[letter] = node
            curr = node
        curr.end = True

   def search(self, word):
        curr = self.root
        for letter in word:
            node = curr.children.get(letter)
            if not node:
                return False
            curr = node
        return curr.end
		
   def all_words_beginning_with_prefix(self, prefix):
        cur = self.root
        for c in prefix:
            cur = cur.children.get(c)
            if cur is None:
                return  

        yield from cur.all_words(prefix)


@application.route('/suggestions', methods=['GET'])
def home():
   empty_dict = {}
   results = {"suggestions": empty_dict}
   if 'q' in request.args:
      city_prefix= request.args['q'].lower()
   else:
     return jsonify(results)
    
   latitude = None
   longitude = None
   if 'latitude' in request.args and 'longitude' in request.args:
      latitude = float(request.args['latitude'])
      longitude = float(request.args['longitude'])
   trie = Trie()
   city_dict = {}
   prov_terr_canada = {
    '01': 'Alberta',
    '02': 'British Columbia',
    '03': 'Manitoba',
    '04': 'New Brunswick',
    '05': 'Newfoundland and Labrador',
	'14': 'Nunavut',
    '07': 'Nova Scotia',
    '08': 'Ontario',
    '09': 'Prince Edward Island',
    '10': 'Quebec',
    '11': 'Saskatchewan',
	'12': 'Yukon',
	'13': 'Northwest Territories'
	}
   # lecture du fichier ligne par ligne
   # remplire les deux structures de donnees la trie et le disctionnaire qui contient toutes les entrees dans le fichier
   with open('cities_canada-usa.tsv',"rt", encoding="utf8") as tsvin:
   # c'est important que la trie utilise la version lowercase pour supporter les prefix peu importe la case utilise
   # pour chaque entree, on construit une entree dans le dictionnaire avec la cle le nom de la ville et la 
   #valeur l objet city
      for line in csv.reader(tsvin, delimiter='\t'):
         trie.insert(line[1].lower())
         if line[8] == 'US':
            country = "USA"
            state = line[10]
         else:
           country = "Canada"
           state = prov_terr_canada[line[10]]
		 # construire l objet city avec les informations pertinentes pour l output et l inserer dans le dictionnaire
         curr_city = City(line[1] + ", " + state + ", " + country, float(line[4]), float(line[5]), int(line[14]))
         city_dict.setdefault(line[1].lower(), []).append(curr_city)
   inter_results = []
   count = 0
   words_with_prefix = list(trie.all_words_beginning_with_prefix(city_prefix))
   for key in words_with_prefix:
      count += len(list(city_dict.get(key)))
   for key in words_with_prefix:
      occ_city = list(city_dict.get(key))
      for occ in occ_city:
         occ.__score__(count, latitude, longitude, city_prefix)
         inter_results.append(occ.__dict__())
   results = {"suggestios": sorted(inter_results, key=itemgetter('score'), reverse=True)}
   return jsonify(results)
   
if __name__ == "__main__":
   application.run()
