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

from utils import *

##################################################################

"Set the start and end year:"
year_in = 1917
#year_in = 2005
year_end = 2009

"If download == False tries to read data from a file:"
downloadQ = False#True#
"If calcDegree == True calclulates degree distributions of the network:"
calcDegree = True#False#

"If calcDegree == True calclulates infomap clustering of the network:"
"Depends on separate Infomap program that needs to be in a subfolder."
infomapQ = True#False#

if downloadQ:
   "Download data if necessary:"

   print 'Downloading data'
   output = downloadTeamRosters(year_in, year_end)

   "Save results:"
   data_file = 'nhl_data_'+str(year_in)+'_'+str(year_end)+'.p'

   f = open(data_file, 'w')
   pickle.dump(output, f)
   f.close()
   teams = output['teams']
   link2name = output['link2name']
   team_active = output['team_active']
   players_uniq = output['players_uniq']
   link2country = output['link2country']
   
else:

   "Read data from file:"
   print 'Reading data'
   data_file = 'nhl_data_'+str(year_in)+'_'+str(year_end)+'.p'
   f = open(data_file, 'r')
   pfile = pickle.load(f)
   teams = pfile['teams']
   link2name = pfile['link2name']
   team_active = pfile['team_active']
   players_uniq = pfile['players_uniq']
   link2country = pfile['link2country']

   f.close()

"California Golden Seals missing from team names:"
for team in teams:
   if team.name == '':
      team.name = 'California Golden Seals'


##################################################################

"Create hash tables for link -> index and index -> link:"
"Note that link is end of the database address of a player."
"These are unique compared to names."
link2id = {}
id2link = {}

for i in xrange(len(players_uniq)):
    link2id[players_uniq[i]] = i
    id2link[i] = players_uniq[i]

"Create a list of Player objects:"
players_list = []

"Note that here player is the link string:"
for player in players_uniq:
   players_list.append(Player(link2name[player],player,[]))

"Add teammates for every player:"
for team in teams:
   tmp = team.players
   for player in team.players:
      nbours = set(tmp)
      "Remove current player from the list:"
      nbours.remove(player)

      for nbour in nbours:
         players_list[link2id[player]].addnbour(nbour)
      players_list[link2id[player]].addteam(team.name)
      players_list[link2id[player]].addyear(team.year)

##################################################################

"Determine unique names of the teams:"
team_names = sorted(set([team.name for team in teams]))

print '\nTotal number of NHL players: ', len(players_uniq)
print 'Total number of NHL teams: ', len(team_names), '\n'

"""Create list of Team_agg classes where an object presents a team
for all the years it has been active:"""
team2id = {}
id2team = {}
for i in xrange(len(team_names)):
   team2id[team_names[i]]=i
   id2team[i]=team_names[i]

teams_list = []

for name in team_names:
   teams_list.append(Team_agg(name))

"Determine the links between teams through the different teams of players:"
for player in players_list:
   if len(player.teams)>1:
      for team in player.teams:
         nbours = set(player.teams)
         nbours.remove(team)
         for nbour in nbours:
            teams_list[team2id[team]].addnbour(nbour)


##################################################################

"""
In the following calculations cumulative degree equals the total number of
teammates a player has had up to that year.
"""

"""Calculate the evolution of players' number of teammates or
   the cumulative degree of a player:"""

print """Calculating the evolution of player's cumulative degree:"""
for player in players_list:
   PlayerTeammatesEvo(teams, player)

"Calculate and plot the time evolution of the roster size:"
RosterEvo(teams, players_list)

"Calculate empirical distribution function of the cumulative degree:"
calcCumulative(teams, players_list)

avg_team = np.mean([len(player.teams) for player in players_list])
print 'Average number of teams of a player:', avg_team


##################################################################

if calcDegree:
   print '\nCreating adjacency matrix'

   "Create adjacency matrix:"
   wij = np.zeros((len(players_list),len(players_list)))

   for i in xrange(len(players_list)):
      player = players_list[i]
      for nbour in player.nbours:
         wij[i][link2id[nbour]] = player.wij[nbour]

   "Mean degree:"
   m_deg = np.mean(np.sum(np.where(wij>0,1,0),axis=1))

   print 'Mean degree of the graph:', m_deg

   "Plot degree distributions for different cutoffs:"
   cut_offs = [0, 1, 2, 3, 4, 5]

   color = get_color()

   for cut_off in cut_offs:
      acolor = next(color)
      plotDegreeDist(wij, cut_off, acolor)

   color = get_color()

   """
   for cut_off in cut_offs:
      acolor = next(color)
      plotDegreeDist(wij, cut_off, acolor, weightQ=True)

   plotcCDFs(cut_offs, wij)
   """

##################################################################

path = os.getcwd() + '/'

print '\nCreating player and team graphs'

G, H = createGraphs(teams_list, players_list, team2id, link2id)

G_name = 'NHL-Player-Network-' + str(year_in) + '-' + str(year_end)
H_name = 'NHL-Team-Network-' + str(year_in) + '-' + str(year_end)


##################################################################

"Do Infomap clustering:"

if infomapQ:

   out_path = path + 'Infomap/output'
   "infomap_path = path to to executable Infomap program."
   infomap_path = path + 'Infomap/Infomap'

   InfomapClustering(players_list, G, H, G_name, H_name,
                     path, infomap_path, out_path)

##################################################################

"Write graphs to gml file:"

write_gml(teams_list, players_list, G, H, G_name, H_name,
          players_uniq, link2country, link2id, team_active,
          path)

##################################################################

actyearQ = False

if actyearQ:
   "Study network of players who are still playing in the year act_year"

   act_year = 2000
   output = activePlayers(teams, players_list, link2name, act_year)
   G_act, H_act = createGraphs(teams_list, output['players'],
                            team2id, output['link2id'])

   G_name = 'NHL-Player-Network-Active-' + str(act_year)

   write_gml(teams_list, output['players'], G_act, H_act, G_name, H_name,
          output['players_uniq'], link2country, output['link2id'],
          team_active, path, writeTeamsQ = False)

print 'Done.'
