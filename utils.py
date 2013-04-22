import numpy as np
import matplotlib.pyplot as plt

try:
   import cPickle as pickle
except:
   import pickle

import re
import requests
from bs4 import BeautifulSoup

import os
from subprocess import call
import csv

import networkx as nx

###############################################################################
# List of functions that are needed when analyzing the NHL affiliation network
###############################################################################

def get_page(url):
   import requests

   r = requests.get(url)
   content = r.text.encode('utf-8', 'ignore')
   return content

def replace_all(text, dic):
   "Use the replacement rules from dictionary dic to text string"
   for i, j in dic.iteritems():
     text = text.replace(i, j)
   return text

class Team:
   """A hockey team class for a given year:
   """
   def __init__(self, name, year, link, players):
     self.name = name
     self.players = players
     self.year = year
     self.link = link

class Team_agg:
   """A hockey team class for all years:
   """
   def __init__(self, name):
      self.name = name
      self.nbours = set([])
      self.wij = {}
   def addnbour(self, team):
     if team in self.nbours:
       self.wij[team]+=1.0
     else:
       self.nbours.add(team)
       self.wij[team]=1.0


class Player:
   """A class for a player:
   """
   def __init__(self, name, link, nbours):
     self.name = name
     self.link = link
     self.nbours = set([])
     self.teams = set([])
     self.years = set([])
     self.wij = {}
     "Dictionary of cumulative number of teammates per year:"
     self.cumu = {}
     "List of Infomap communities:"
     self.communities = []
   def addnbours(self, list_players):
     self.nbours.update(list_players)
   def addnbour(self, player):
     if player in self.nbours:
       self.wij[player]+=1.0
     else:
       self.nbours.add(player)
       self.wij[player]=1.0
   def addteam(self, team):
     self.teams.add(team)
   def addyear(self, year):
     self.years.add(year)
   def add2com(self, com_list):
     self.communities.extend(com_list)
   def add_cumu(self, res):
     self.cumu = res
     

def downloadTeamRosters(year_in, year_end):
   """Download rosters of all NHL teams between years year_in and year_end.
     Return a dictionary with the necessary data of players and teams."""

   teams = []
   match = re.compile('teams/teamyear.htm\?tm=[A-Za-z]+&yr=')
   match_player = re.compile(('/players/playerpage.htm\?ilkid='))
   match_country = re.compile('bycountry.htm\?code=[A-Za-z]*')

   link2name = {}
   team_active = {}

   for year in xrange(year_in,year_end+1):
     url = ('http://www.databasehockey.com/leagues/leagueyear.htm?yr='
          +str(year))

     "Get html code for the year:"     
     html_code = get_page(url)
     soup = BeautifulSoup(html_code)

     links = []
     
     for link in soup.findAll('a'):
       "Find all links that match search criteria for teams:"
       try:
         href = link['href']
         if re.search(match, href):
            links.append(('http://www.databasehockey.com'+href))
       except KeyError:
         pass

     "Remove multiple links:"
     links = sorted(set(links))

     for i in xrange(len(links)):
       link = links[i]
       html_team_code = get_page(link)
       soup_team = BeautifulSoup(html_team_code)
       name1 = str(soup_team.find('font',size="+2").b.a.get_text())
       tmp = name1.split(' (')
       name = tmp[0]
       if len(tmp)>1:
         active = tmp[1]
         team_active[name] = active

       print 'Team = ', name, ', season = ', str(year)+'-'+str(year+1)

       players = []

       "Use href links to identify players. Names are not unique."      
       for link_player in soup_team.findAll('a'):
         try:
            href = link_player['href']
            if re.search(match_player, href):
              player_name = link_player.get_text().replace(u'\xa0',' ')
              players.append(href)
              link2name[href]=str(player_name)

         except KeyError:
            pass
       teams.append(Team(name, year, link, players))


   "Determine unique player links (ids) (Note that names are not unique):"
   all_players = []
   for team in teams:
     all_players.extend(team.players)

   players_uniq = sorted(set(all_players))

   "Dictionary that links a player id link to a country:"
   link2country = {}
   
   print "\nFinding the countries of the players:"

   "Get html code for the list of countries:"
   url = 'http://www.databasehockey.com/players/playercountry.htm'
   html_coun = get_page(url)
   soup_coun = BeautifulSoup(html_coun)

   link_countries = []
   "Dictionary to link country links to names of the countries:"
   linkcoun2country = {}
   for link in soup_coun.findAll('a'):
     "Find all links that match search criteria for countries:"
     try:
       href = link['href']
       if re.search(match_country, href):
         link_countries.append(href)
         linkcoun2country[href] = str(link.get_text().replace(u'\xa0',' '))
     except KeyError:
       pass

   "Remove multiple links:"
   link_countries = sorted(set(link_countries))

   "Download player list for every country:"
   for i in xrange(len(link_countries)):
     link = link_countries[i]
     "Nationality:"
     nat = linkcoun2country[link]
     print 'Downloading country ', linkcoun2country[link]
     html_nation = get_page('http://www.databasehockey.com'+link)
     soup_nation = BeautifulSoup(html_nation)

     "Use href links to identify players. Names are not unique."      
     for link_player in soup_nation.findAll('a'):
       try:
         href = link_player['href']
         if re.search(match_player, href):
            link2country[href] = nat
       except KeyError:
         pass

   output = {}
   output['teams'] = teams
   output['link2name'] = link2name
   output['team_active'] = team_active
   output['players_uniq'] = players_uniq
   output['link2country'] = link2country

   return output


def findPlayer(players_list, searchstring):
   "Search for players by name:"

   tmp = [i for i in xrange(len(players_list))
          if searchstring in players_list[i].name]

   return tmp
   

def activePlayers(teams, players_list, link2name, act_year):
   "Calculate the network of active players in the year act_year:"
   active_plrs = []

   for player in players_list:
      if act_year in player.years:
         active_plrs.append(player.link)

   active_plrs = sorted(set(active_plrs))

   "Create hashtable for link -> id and id -> link."
   link2idact = {}
   idact2link = {}

   for i in xrange(len(active_plrs)):
      link2idact[active_plrs[i]] = i
      idact2link[i] = active_plrs[i]


   active_list = []
   for link in active_plrs:
      active_list.append(Player(link2name[link],link,[]))

   "Add teammates for active players:"
   for team in teams:
      if team.year <= act_year:
         tmp = set(team.players).intersection(active_plrs)
         for player in tmp:
            nbours = set(tmp)
            #"Remove current player from the list:"
            nbours.remove(player)

            if len(nbours)>0:
               for nbour in nbours:
                  active_list[link2idact[player]].addnbour(nbour)
               active_list[link2idact[player]].addteam(team.name)
               active_list[link2idact[player]].addyear(team.year)


   output = {}
   output['year'] = act_year
   output['link2id'] = link2idact
   output['id2link'] = idact2link
   output['players'] = active_list
   output['players_uniq'] = active_plrs

   return output


def RosterEvo(teams, players_list):
   "Plot the evolution of the number of teams and team roster size:"

   "Years NHL has been active:"
   path = os.getcwd() + '/plots/'
   "Test if folder exists:"
   if not os.path.isdir(path):
     os.makedirs(path)

   years = sorted(set([team.year for team in teams]))

   teams_num = []

   for year in years:
     tmp = []
     for team in teams:
       if team.year == year:
         tmp.append(team.name)
     teams_num.append(len(set(tmp)))

   plt.title('Evolution of the number of teams in the NHL')
   plt.xlabel('year')
   plt.ylabel('Number of teams')
   
   plt.ylim([0,34])
   plt.plot(years,teams_num)

   plt.savefig(path+'teams_num.pdf',
            format='pdf')

   plt.clf()

   "Calculate average number of players in a team in a year:"
   players_team_avg = []
   for year in years:
     tmp = []
     for team in teams:
       if team.year == year:
         tmp.append(len(team.players))
     players_team_avg.append(np.mean(tmp))


   plt.title('Roster size evolution')
   plt.xlabel('year')
   plt.ylabel('Average number of players in a team')
   
   plt.plot(years,players_team_avg)
   plt.savefig(path+'roster_size.pdf',
            format='pdf')

   plt.clf()

   "Calculate the evolution of the total number of players in the league:"
   np_dict = {}

   for i in xrange(len(years)):
      np_dict[years[i]] = 0.0
   
   for player in players_list:
      for year in player.years:
         np_dict[year] += 1.0
         
   num_players = [np_dict[x] for x in years]

   plt.title('Total number of players in the league')
   plt.xlabel('year')
   plt.ylabel('Number of players')
   
   plt.plot(years,num_players)
   plt.savefig(path+'players_num.pdf',
            format='pdf')

   plt.clf()



def PlayerTeammatesEvo(teams, player):
   """Calculate the number of unique teammates a player has had up to a year."""

   cumu_dict = {}

   "Select only teams in which the player is:"
   players_teams = []
   for team in teams:
     if player.link in team.players:
       players_teams.append(team)

   players_teams = sorted(players_teams,key = lambda team: team.year)

   years_p = [team.year for team in players_teams]
   "Calculate the cumulative number of player's teammates over years:"

   mates = [set([]).union(*[team.players for team in players_teams[:i]])
         for i in xrange(1,len(players_teams)+1)]

   for x in mates:
     x.remove(player.link)

   for i in xrange(len(years_p)):
     year = years_p[i]
     if year in cumu_dict.iterkeys():
       if cumu_dict[year] < len(mates[i]):
         cumu_dict[year] = len(mates[i])
     else:
       cumu_dict[year] = len(mates[i])

   player.add_cumu(cumu_dict)


def calcCumulative(teams, players_list):
   """Calculate and plot variables that are related to players
   cumulative degree.
   teams = list of Team objects
   players_list = list of Player objects
   """
   
   path = os.getcwd() + '/plots/'
   "Test if folder exists:"
   if not os.path.isdir(path):
     os.makedirs(path)

   """Calculate how the average cumulative degree of the players has evolved
   over time:"""
   years = sorted(set([team.year for team in teams]))

   data = []
   for year in years:
     tmp = []
     for player in players_list:
       if year in player.years:
         tmp.append(player.cumu[year])
     data.append(np.mean(tmp))

   plt.title('Average cumulative degree in the league')
   plt.xlabel('year')
   plt.ylabel('Average cumulative degree')

   plt.plot(years,data)

   plt.savefig(path+'ave_cumu_deg.pdf', format='pdf')
   plt.clf()


   "Calculate annual changes in degree for all players:"
   data2 = []

   for player in players_list:
     years_p = sorted(player.cumu.iterkeys())
     data2.extend(list(np.diff([player.cumu[year] for year in years_p])))

   "Calculate the empirical CDF distribution:"
   a, b = cdfx(data2)

   p_title = ('Distribution of changes in players cumulative degree\n during'+
         ' one season')
   plt.title(p_title)
   plt.xlabel(r'$\Delta$ degree')

   "Calculate the empirical PDF distribution as differences:"
   plt.plot(a[1:],np.diff(b)/np.diff(a))

   plt.savefig(path+'delta_degree_dist.pdf', format='pdf')
   plt.clf()



def plotDegreeDist(wij, cutoff, acolor, weightQ=False):
   """Plot the degree distribution for adjacency matrix wij
     with values less than cutoff set to zero.
     acolor determines the color of the curve.
     main_path = path to the folder where to write the image."""

   import matplotlib.pyplot as plt
   import os
   import datetime

   path = os.getcwd() + '/plots/'
   "Test if folder exists:"
   if not os.path.isdir(path):
     os.makedirs(path)

   plt.clf()

   fig = plt.figure(1)

   plt.title('Degree distribution')
   plt.xlabel('Degree')
   plt.ylabel('Fraction of players')

   plt.xscale('log')
   plt.yscale('log')
   if weightQ:
      deg = np.sum(np.where(wij>cutoff,wij,0),axis=1)
   else:
      deg = np.sum(np.where(wij>cutoff,1,0),axis=1)
   deg2 = sorted(set(deg))
   counts = 1.0/len(deg)*np.array(map(list(deg).count,deg2))

   "This is not optimal:"
   #plt.xlim([0.9,max(deg2)+10])
   #plt.ylim([0.9,max(counts[1:])+10])

   plt.scatter(deg2[1:], counts[1:], label='cutoff = ' + str(cutoff),
               color = acolor, alpha=0.9)

   plt.legend()

   if weightQ:
      fig.savefig(path+'w_degree_dist_cutoff_'+str(cutoff)+'.pdf',
            format='pdf')
   else:
      fig.savefig(path+'degree_dist_cutoff_'+str(cutoff)+'.pdf',
            format='pdf')

   plt.clf()

   return [deg2, counts]

def plotDegreePDF(wij, cutoff, acolor):
   """Plot the degree distribution for adjacency matrix wij
     with values less than cutoff set to zero.
     acolor determines the color of the curve.
     main_path = path to the folder where to write the image."""

   import matplotlib.pyplot as plt
   import os
   import datetime

   path = os.getcwd() + '/plots/'
   "Test if folder exists:"
   if not os.path.isdir(path):
     os.makedirs(path)

   plt.clf()

   plt.title('Degree distribution')
   plt.xlabel('k')
   #plt.ylabel('Number of occurrences')

   plt.yscale('log')
   data = np.sum(np.where(wij>cutoff,1,0),axis=1)

   a,b = cdfx(data)
     
   plt.scatter(a[1:],np.diff(b)/np.diff(a),
            label='cutoff = ' + str(cutoff),
            color = acolor,alpha=0.9)

   plt.legend()

   plt.savefig(path+'degree_dist_cutoff_'+str(cutoff)+'.pdf',
            format='pdf')

   plt.clf()


def plotcCDFs(cutoffs, wij):
   "Plot complementary empirical CDF functions for the degree distribution:"

   import matplotlib.pyplot as plt

   path = os.getcwd() + '/plots/'
   "Test if folder exists:"
   if not os.path.isdir(path):
      os.makedirs(path)

   for cutoff in cutoffs:
      data = np.sum(np.where(wij>cutoff,1,0),axis=1)

      a,b = cdfx(data, comp=True)
      plt.plot(a,b,label=r'$\rho = $' + str(cutoff))

   plt.title('Complementary empirical CDF functions')
   plt.xlabel('k')
   plt.ylabel('P(degree>k)')
   plt.legend()

   plt.xscale('log')
   plt.yscale('log')
   plt.savefig(path+'cCDFs.pdf', format='pdf')
   plt.clf()


def cdfx(data, comp=False):
   "Calculate empirical cdf or the complementary cdf:"

   tmp = sorted(set(data))
   data_tmp = list(data)
   counts = np.array(map(data_tmp.count,tmp),np.float64)

   if comp:
     return tmp, 1.0 - np.cumsum(counts)/len(data)
   else:
     return tmp, np.cumsum(counts)/len(data)


def get_color():
   for item in ['r', 'g', 'b', 'c', 'm', 'y', 'k']:
      yield item

#####################################################################
# List of functions related to graphs
#####################################################################

def createGraphs(teams_list, players_list, team2id, link2id):
   "Create graphs for players and teams:"
   import networkx as nx
   
   "Create a graph for players:"
   G = nx.empty_graph(len(players_list), create_using = None)
   
   "Id nodes by player link:"
   for i in xrange(len(players_list)):
      G.node[i]['label']=i

      for player in players_list[i].nbours:
         G.add_edge(i,link2id[player],weight=players_list[i].wij[player])

   "Create a graph for teams:"
   H = nx.empty_graph(len(teams_list), create_using = None)

   for i in xrange(len(teams_list)):
      H.node[i]['label']=i

      for team in teams_list[i].nbours:
          H.add_edge(i,team2id[team],weight=teams_list[i].wij[team])

   return G, H


def findPlayerDistances(G, player_name, pathQ=False):
   """Find players distances to others in the graph.
      If pathQ = True returns a dictionary of the shortest paths,
      else returns distances."""
   import networkx as nx

   pos = findPlayer(players_list,player_name)
   go = False
   if len(pos)>1:
      print 'Found players ', [players_list[i].name for i in pos]
      print 'Please use more specific name.'
   elif len(pos)==1:
      print 'Found player', players_list[pos[0]].name
      go = True
   else:
      print 'No players found.'

   if go:
      res = nx.single_source_dijkstra(G, pos[0])
      if pathQ:
         return res[1]
      else:
         return res[0]

      

def InfomapClustering(players_list, G, H, G_name, H_name,
                 path, infomap_path, out_path):
   """This function calls Infomap to cluster the player and team networks.
      players_list = list of Player objects,
      G = player networkx graph
      H = team networkx graph,
      G_name = name of player graph, string
      H_name = name of team graph, string
      infomap_path = path of the executable Infomap program.
      out_path = path where Infomap writes the results."""

   import os
   from subprocess import call
   import csv

   "Write graphs to pajek files:"

   G_file = path + 'Infomap/' + G_name.lower() + '.net'
   H_file = path + 'Infomap/' + H_name.lower() + '.net'
   
   nx.write_pajek(G, G_file)
   nx.write_pajek(H, H_file)

   "Uckly hack to remove the first line from the pajek files:"
   g = open(G_file,"r")
   g_lines = g.readlines()
   g.close()
   
   g = open(G_file,"w")
   for i in xrange(1,len(g_lines)):
      g.write(g_lines[i])
   g.close()

   h = open(H_file,"r")
   h_lines = h.readlines()
   h.close()
   
   h = open(H_file,"w")
   for i in xrange(1,len(h_lines)):
      h.write(h_lines[i])
   h.close()

   try:
      print '\nCalculating Infomap clustering for player graph'

      "Test if folder exists:"
      if not os.path.isdir(out_path):
         os.makedirs(out_path)

      "Cluster the network ten times:"

      call([infomap_path,'--input-format=pajek',
           G_file, out_path,'-N', '10'])

      G_out = out_path + '/' + G_name.lower() + '.map'

      outfile = csv.reader(open(G_out, "rU"),delimiter=' ')
      outfile.next()

      lines = []
      for row in outfile:
         lines.append(row)

      "Determine the range of lines where node data is:"
      for i in xrange(len(lines)):
         if '*Nodes' in lines[i]:
            i0 = i
         if '*Links' in lines[i]:
            i1 = i

      for i in xrange(i0+1,i1):
         line = lines[i]
         "List of communities of the node:"
         coms = [int(x) for x in line[0].split(':')]
         player_id = int(line[1])
         "Add player to community:"
         players_list[player_id].add2com(coms)
         G.node[player_id]['comm_1']=coms[0]
         G.node[player_id]['comm_2']=coms[1]

      print '\nCalculating Infomap clustering for team graph'
     
      "Cluster the network ten times:"

      call([infomap_path,'--input-format=pajek',
           H_file, out_path,'-N', '10'])

      H_out = out_path + '/' + H_name.lower() + '.map'

      outfile = csv.reader(open(H_out, "rU"),delimiter=' ')
      outfile.next()

      lines = []
      for row in outfile:
         lines.append(row)

      "Determine the range of lines where node data is:"
      for i in xrange(len(lines)):
       if '*Nodes' in lines[i]:
         i0 = i
       if '*Links' in lines[i]:
         i1 = i

      for i in xrange(i0+1,i1):
         line = lines[i]
         "List of communities of the node:"
         coms = [int(x) for x in line[0].split(':')]
         team_id = int(line[1])
         "Add player to community:"
         H.node[team_id]['comm_1']=coms[0]
         H.node[team_id]['comm_2']=coms[1]

     
   except:
      print 'Infomap not found or not working.'
      pass

def write_gml(teams_list, players_list, G, H, G_name, H_name,
           players_uniq, link2country, link2id, team_active,
           path, writeTeamsQ = True):
   """Write networkx graphs G and H as gml files to disk.
      teams_list = list of Team objects
      players_list = list of Player objects
      G = player networkx graph
      H = team networkx graph
      G_name = name of player graph, string
      H_name = name of team graph, string
      players_uniq = list of unique player links
      link2country = hashtable for player link -> country
      link2id = hashtable for player link -> number of player in players_list
      """
   import networkx as nx

   G.name = G_name 

   print '\nWriting gml graphs:'

   for i in xrange(len(players_list)):
      G.node[i]['name']=players_list[i].name
      G.node[i]['years_active']=', '.join([str(x) for x in
                                 sorted(players_list[i].years)])
      G.node[i]['team_list']=','.join([str(x) for x in
                              sorted(players_list[i].teams)])
      G.node[i]['teams'] = len(players_list[i].teams)


   "id values for which no country data available:"
   not_found = set(players_uniq).copy()
   not_found.difference_update(link2country.keys())

   for link in not_found:
      G.node[link2id[link]]['country']='N/A'
   
   "id values for which country data was available:"
   found = set(players_uniq).copy()
   found.intersection_update(link2country.keys())

   for link in found:
      G.node[link2id[link]]['country']=link2country[link]

   "Write graph to file:"   
   filen = path + G.name.lower() + '.gml'
   nx.write_gml(G, filen)

   if writeTeamsQ:
      H.name = H_name

      for i in xrange(len(teams_list)):
         H.node[i]['name'] = teams_list[i].name
         H.node[i]['active'] = team_active[teams_list[i].name]

      filen2 = path + H.name.lower() + '.gml'
      nx.write_gml(H, filen2)

