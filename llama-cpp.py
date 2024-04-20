#!/usr/bin/env python3
import difflib
import math
import sqlite3
import sys
import time
import re
import random
import traceback

import requests
import json

url = 'http://192.168.1.82:8080/completion'

db_file = 'media2.db'

prompt = """
You are a helpful assistant to 'User'. You do not respond as 'User' or pretend to be 'User'. You only respond once as 'Assistant'. 'System' will give you data. Do not respond as 'System'. Always explain why you do what you do with lines starting with 'Thoughts:'.
You control a tvbox. You have the list of tv shows available, and can browse the full catalogue. Prefer recent content. Your role is to chose which file matches the user's request and play it with a very short answer, using JSON commands.
Finish every command with </s>
If the episode to play is ambiguous, take into consideration the latest episode the user watched for this TV show. And play the next one.
The user doesn't necessarily talk directly about the name of the show, they might refer to a character in the show, an object, or an event.

Never suppose your knowledge is up-to-date, always do database requests to confirm. The IDs in the examples are wrong.
DO NOT reuse the id seen in the examples.
Stop on the first request, do not continue the conversation.
The id in the examples are fake. Ask again for the id.

Always search for the TV show ID before trying to find which episode to play.
If the user seem to request a specific episode, always try to open that episode.
Do the searches with short keyword queries, remove articles or redundant information.
If the search failed, search again but with variations of the search keywords. If it still fails, browse the full list.

If a search fails, maybe try to translate that search in english.
All full text search only outputs the first 5 results. Full text search will only show the result containing all the keywords.

Available functions are:
- list_tvshows: List of TV Shows in the database. Example: {"function":"list_tvshows"}</s> returns [{"id":3948, "name":"Doctor who"},{"id":12, "name":"Brooklynn Nine-Nine"}]
- search_tvshow: Full-text-search for a TV Series (not episodes). Example: {"function":"search_tvshow","query":"doctor sci-fi"}</s> returns [{"id":2341,"name":"Doctor Who","genres":"sci-fi"},{"id":42,"name":"Condor"},{"id":32,"name":"Doctor Who 1963"},{"id":39,"name":"Industry"},{"id":11,"name":"Sex Education"}]
- get_tvshow_details: Get full details (including genre, actors, rating, ...) of a tvshow.  
- list_seasons_in_tvshow: Get the list of seasons within a TV show, including the number of episodes in the season. Example: {"function":"list_seasons_in_tvshow", "tvshow_id":12}</s> returns [{"s":1", n":10}]
- list_episodes_in_season: Get the list of episodes with description within a TV show season. Example: {"function":"list_episodes_in_season", "tvshow_id":1,"season":1}</s> returns [{"episode":1, "name":"Rose","plot":"When ordinary shop-worker Rose Tyler meets a mysterious stranger called the Doctor she is drawn into his strange and dangerous world; her life will never be the same again."}, ...]
- list_episodes: Get the list of episodes with description within a TV show across all season. Example: {"function":"list_episodes", "tvshow_id":93}</s> returns [{"season":1,"episode":1, "name":"Rose","plot":"When ordinary shop-worker Rose Tyler meets a mysterious stranger called the Doctor she is drawn into his strange and dangerous world; her life will never be the same again."}, ...]
- get_episodes_infos: Get more informations about a TV show episode, including actors, directors and writers: {"function":"get_episodes_infos", "tvshow_id":3442, "season":1, "episode":1}</s> returns {"plot":"We discover rose", "actors": "Billie Piper, Christopher Eccleston", "writers": "Russell T. Davies"}
- search_episode_in_season: Full-Text-Search for an episode in a season. Example: {"function":"search_in_tvshow_season", "tvshow_id":298,"season":1,"query":"jail"}</s> returns {"episode":1,"plot":"Rose goes to jail"}
- search_episode_in_tvshow: Full-Text-Search for an episode in a TV Show. Example: {"function":"search_in_tvshow", "tvshow_id":314,"query":"jail"}</s> returns {"season":1,"episode":1,"plot":"Rose goes to jail"}
- play_episode: Launch the playback of an episode. Example: {"function":"play_episode","tvshow_id":1234,"season":1,"episode":1}</s>
- play_latest_episode: Launch the playback of the most recent episode of a tvshow. Example: {"function":"play_episode","tvshow_id":758}</s>
- continue_tvshow: Launch the playback of the next episode to view for that tvshow. Example: {"function":"continue_tvshow","tvshow_id":1234}</s>
- say: Answer to the user {"function":"say","message":"Here is that awesome Moffat episode"}</s>
- end: End the conversation. Example: {"function":"end"}</s>

Another example:
User: watch doctor goodwin
Thoughts: I search for user's "doctor Goodwin" tvshow
Assistant: {"function":"search_tvshow","query":"doctor goodwin"}
System: [{"id": 37, "name": "New Amsterdam", "rating": 8.399999618530273, "genres": "Drama", "plot": "The new medical director breaks the rules to heal the system at America's oldest public hospital. Max Goodwin sets out to tear up the bureaucracy and provide exceptional care, but the doctors and staff are not so sure he can succeed. They've heard this before. Not taking \"no\" for an answer, Dr. Goodwin's instinctive response to problems large and small is four simple words: \"How can I help?\" He has to disrupt the status quo and prove he'll stop at nothing to breathe new life into this underfunded and underappreciated hospital, returning it to the glory that put it on the map."}, {"id": 50, "name": "What If", "rating": 7.0, "genres": "Comedy"}, {"id": 74, "name": "Last Week Tonight with John Oliver", "rating": 7.900000095367432, "genres": "Talk, Comedy, News"}, {"id": 45, "name": "Extrapolations", "rating": 5.900000095367432, "genres": "Drama"}, {"id": 20, "name": "Brave New World 2014", "rating": 0.0, "genres": null}]
Thoughts: The user asked for "goodwin" but the closest match in the database is "New Amsterdam" which has Max Goodwin as a character and doctors, I'll assume the user meant that TV show and I'll play the next episode for the user.
Assistant: {"function":"continue_tvshow","tvshow_id":37}
System: "Playing episode"

Another example:
User: watch the doctor blink
Thoughts: The user asked for "doctor blink", I'll search for "doctor" TV show and then search for "blink" episode
Assistant: {"function":"search_tvshow","query":"doctor"}
System: [{"id": 9394, "name": "Doctor Who"},...]
Thoughts: The closest TV Show seems to be the one with id 9394, let's search for the "blink" episode
Assistant: {"function":"search_episode_in_tvshow","tvshow_id":9394,"query":"blink"}
System: [{"season": 5, "episode": 4, "title": "The Time of Angels (1)"}, {"season":3, "episode": 10, "title": "Blink"}]
Thoughts: The user asked for "doctor blink" and the closest match in the database is "Doctor Who" with an episode named "blink", I'll assume the user meant that episode and I'll play it
Assistant: {"function":"play_episode","tvshow_id":31,"season":3,"episode":10}
System: "Playing episode"

Another example:
User: regarder les femmes conservatrices des annees 50
Thoughts: The user asked in french for a show about conservative women in the 50s
Assistant: {"function":"search_tvshow","query":"conservatrices 50"}
System: []
Thoughts: Let's searching in english
Assistant: {"function":"search_tvshow","query":"conservatices 50s"}
System: [{"id": 3984, "name": "Mrs. America", "plot": "The true story of the movement to ratify the Equal Rights Amendment, and the unexpected backlash led by a conservative woman named Phyllis Schlafly, aka “the sweetheart of the silent majority.”"}]
Assistant: {"function":"continue_tvshow","tvshow_id":3984}
System: "Playing episode"

You may try to answer unrelated questions:
User: What's 1+1 ?
Thoughts: Okay that's 2
Assistant: {"function":"say","message":"2"}</s>
Thoughts: Let's stop here
Assistant: {"function":"end"}</s> 

"""

# Here is an example on how to answer the user's request:
# User: Watch the latest Last Week Tonight
# Thoughts: I search for user's "Last Week Tonight" tvshow
# Assistant: {"function":"search_tvshow","query":"last week tonight"}</s>
# System: [{"id":74,"name":"Last Week Tonight with John Oliver"},{"id":8,"name":"Batwoman"},{"id":48,"name":"Black Mirror"},{"id":29,"name":"His Dark Materials"},{"id":66,"name":"Bonding"}]
# Thoughts: Okay, the closest TV Show seems to be the one with id 3, let's list its seasons.
# Assistant: {"function":"list_seasons_in_tvshow","tvshow_id":3}</s>
# System: [{"s":1,"n":4},{"s":2,"n":6}]
# Thoughts: Most recent season is Season 2, let's list its episodes.
# Assistant: {"function":"list_episodes_in_season","tvshow_id":3,"season":2}</s>
# System: [{"episode":1,"name":"Episode 1","plot":"This is the plot of the first episode"},{"episode":2,"name":"Episode 2","plot":"This is the plot of the second episode"}]
# Thoughts: This must be the one with the highest number, season 2 episode 2. Let's play it
# Thoughts: And say something nice to the user
# Assistant: {"function":"say","message": "Enjoy that episode!"}</s>
# Assistant: {"function":"play_episode","tvshow_id":4,"season":2,"episode":5}</s>
# System: "Starting episode"
#
# Another example:
# User: Watch Supergirl
# Thoughts: I search for user's "Supergirl" tvshow
# Assistant: {"function":"search_tvshow","query":"supergirl"}</s>
# System: [{"id":23,"name":"Supergirl"}]
# Thoughts: Okay, the closest TV Show seems to be the one with id 23, let's see what the next episode for the user
# Assistant: {"function":"get_user_next_episode_for_tvshow","tvshow_id":23}</s>
# System: {"season":3,"episode":22}
# Thoughts: Okay, the next episode for the user is S3E22, let's play it
# Assistant: {"function":"play_episode","tvshow_id":23,"season":3,"episode":22}</s>
# System: "Starting episode"

# Another example:
# User: Watch Scrubs S1E3
# Thoughts: I search for user's "scrubs" tvshow
# Assistant: {"function":"search_tvshow","query":"scrubs"}</s>
# System: [{"id":5,"name":"Scrubs"},{"id":28,"name":"Mythic Quest"},{"id":46,"name":"Most Dangerous Game"},{"id":25,"name":"Trust Me 2017"},{"id":39,"name":"Industry"}]
# Thoughts: Okay, the closest TV Show seems to be the one with id 5, let's list its seasons.
# Assistant: {"function":"list_seasons_in_tvshow","tvshow_id":5}</s>
# System: [{"s":1,"n":2},{"s":2,"n":2}]
# Thoughts: Okay the season 1 the user want exists, let's list its episodes.
# Assistant: {"function":"list_episodes_in_season","tvshow_id":5,"season":1}</s>
# System: [{"episode":8,"plot":"J.D. and Turk become heroes after [...]"},{"episode":6,"plot":"Dr. Cox is still facing the [...]"},{"episode":11,"plot":"It's Christmas, and even though J.D. and t[...]"}]
# Thoughts: Okay, user requested season 1 episode 3, and it's there! Let's play it
# Assistant: {"function":"play_episode","tvshow_id":5,"season":1,"episode":3}</s>
# System: "Starting episode"

# - list_tvshows: List of TV Shows in the database. Example: {"function":"list_tvshows"}</s> returns [{"id":3948, "name":"Doctor who"},{"id":12, "name":"Brooklynn Nine-Nine"}]
# - search_tvshow: Search for a TV Series (not episodes) by anything, name, plot, genre, actors. Example: {"function":"search_tvshow","query":"doctor sci-fi"}</s> returns [{"id":2341,"name":"Doctor Who","genres":"sci-fi"},{"id":42,"name":"Condor"},{"id":32,"name":"Doctor Who 1963"},{"id":39,"name":"Industry"},{"id":11,"name":"Sex Education"}]
# - list_seasons_in_tvshow: Get the list of seasons within a TV show, including the number of episodes in the season. Example: {"function":"list_seasons_in_tvshow", "tvshow_id":12}</s> returns [{"s":1", n":10}]
# - list_episodes_in_season: Get the list of episodes with description within a TV show season. Example: {"function":"list_episodes_in_season", "tvshow_id":1,"season":1}</s> returns [{"episode":1, "name":"Rose","plot":"When ordinary shop-worker Rose Tyler meets a mysterious stranger called the Doctor she is drawn into his strange and dangerous world; her life will never be the same again."}, ...]
# - list_episodes: Get the list of episodes with description within a TV show across all season. Example: {"function":"list_episodes", "tvshow_id":93}</s> returns [{"season":1,"episode":1, "name":"Rose","plot":"When ordinary shop-worker Rose Tyler meets a mysterious stranger called the Doctor she is drawn into his strange and dangerous world; her life will never be the same again."}, ...]
# - get_episodes_infos: Get more informations about a TV show episode, including actors, directors and writers: {"function":"get_episodes_infos", "tvshow_id":3442, "season":1, "episode":1}</s> returns {"plot":"We discover rose", "actors": "Billie Piper, Christopher Eccleston", "writers": "Russell T. Davies"}
# - search_episode_in_season: Search for an episode in a season. Example: {"function":"search_in_tvshow_season", "tvshow_id":298,"season":1,"match":"jail"}</s> returns {"episode":1,"plot":"Rose goes to jail"}
# - search_episode_in_tvshow: Search for an episode in a season. Example: {"function":"search_in_tvshow", "tvshow_id":314,"match":"jail"}</s> returns {"season":1,"episode":1,"plot":"Rose goes to jail"}
# - play_episode: Launch the playback of an episode. Example: {"function":"play_episode","tvshow_id":1234,"season":1,"episode":1}</s>
# - get_user_next_episode_for_tvshow: Get the next episode the user will watch for a TV show. Example: {"function":"get_user_next_episode_for_tvshow","tvshow_id":594}</s> returns {"season":3,"episode":5}
# - say: Answer to the user {"function":"say","message":"Here is that awesome Moffat episode"}</s>
# - end: End the conversation. Example: {"function":"end"}</s>

# XXX WARNING: Grammar is currently outdated !
# This is left here as a reference
grammar = '''
root   ::= innerThought cmd-line

innerThought ::= "Thoughts: " [^\\n]* "\\n"
cmd-line ::= "Assistant: " cmd "\\n"

space ::= " "?
string ::=  "\\"" (
        [^"\\\\] |
        "\\\\" (["\\\\/bfnrt] | "u" [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F])
      )* "\\"" space
integer ::= ("-"? ([0-9] | [1-9] [0-9]*)) space

0 ::= "{" space "\\"function\\"" space ":" space "\\"list_tvshows\\"" "}"
1 ::= "{" space "\\"function\\"" space ":" space "\\"search_tvshow\\""                     "," space "\\"query\\"" space ":" space string     "}"
2 ::= "{" space "\\"function\\"" space ":" space "\\"list_seasons_in_tvshow\\""           "," space "\\"tvshow_id\\"" space ":" space integer "}"
3 ::= "{" space "\\"function\\"" space ":" space "\\"list_episodes_in_season\\""          "," space "\\"tvshow_id\\"" space ":" space integer "," space "\\"season\\"" space ":" space integer "}"
4 ::= "{" space "\\"function\\"" space ":" space "\\"list_episodes\\""          "," space "\\"tvshow_id\\"" space ":" space integer "}"
5 ::= "{" space "\\"function\\"" space ":" space "\\"get_episodes_infos\\""               "," space "\\"tvshow_id\\"" space ":" space integer "," space "\\"season\\"" space ":" space integer "," space "\\"episode\\"" space ":" space integer  "}"
6 ::= "{" space "\\"function\\"" space ":" space "\\"search_episode_in_season\\""         "," space "\\"tvshow_id\\"" space ":" space integer "," space "\\"season\\"" space ":" space integer "," space "\\"query\\"" space ":" space string     "}"
7 ::= "{" space "\\"function\\"" space ":" space "\\"search_episode_in_tvshow\\""         "," space "\\"tvshow_id\\"" space ":" space integer "," space "\\"query\\"" space ":" space string   "}" 
8 ::= "{" space "\\"function\\"" space ":" space "\\"play_episode\\""                     "," space "\\"tvshow_id\\"" space ":" space integer "," space "\\"season\\"" space ":" space integer "," space "\\"episode\\"" space ":" space integer  "}"
9 ::= "{" space "\\"function\\"" space ":" space "\\"get_user_next_episode_for_tvshow\\"" "," space "\\"tvshow_id\\"" space ":" space integer "}"
10 ::= "{" space "\\"function\\"" space ":" space "\\"say\\"" "," space "\\"message\\"" space ":" space string "}"
11 ::= "{" space "\\"function\\"" space ":" space "\\"end\\"" "}"
12 ::= "{" space "\\"function\\"" space ":" space "\\"continue_tvshow\\"" "," space "\\"tvshow_id\\"" space ":" space integer "}"
cmd ::= 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12
'''

separators = "[ ().,;:!?-]"


def nmatches(s1, s2):
    # TODO: lemmizer?
    # TODO: remove stopwords
    # TODO: remove punctuation
    # TODO: remove accents
    # TODO: remove plurals
    a1 = re.split(separators, s1.lower())
    a2 = re.split(separators, s2.lower())
    return len(set(a1) & set(a2))


# Take an object, concatenate all its fields with spaces for full text search
def concat_fields(obj):
    concat = " ".join([str(x) for x in obj.values()])
    return concat


def embedding(content):
    data = {
        'content': content,
    }

    headers = {'Content-Type': 'application/json'}
    response = requests.post('http://192.168.1.82:8080/embedding', data=json.dumps(data), headers=headers)
    return json.loads(response.text)['embedding']


# The goal is that the generated dataset don't always have the same tvshow_id
# To do that, we'll generate a new random tvshow_id, and save in a dict the mapping between the original tvshow_id and the new one
tvshow_id_random = {}


def randomize_tvshowid(tvshow_id):
    if tvshow_id in tvshow_id_random:
        return tvshow_id_random[tvshow_id]
    new_tvshow_id = random.randint(1, 10000)
    while new_tvshow_id in tvshow_id_random.values():
        new_tvshow_id = random.randint(1, 10000)
    tvshow_id_random[tvshow_id] = new_tvshow_id
    return new_tvshow_id


def unrandomize_tvshowid(tvshow_id):
    for k, v in tvshow_id_random.items():
        if v == tvshow_id:
            return k
    return None


# Do a generic full-text search of a textual request into a list of objects
# This function will always return results, even if they are irrelevant
# This will remove fields irrelevant to the search, except those inside always_keep
def generic_search(list_of_objs, request, always_keep):
    nmatches_distances = [(item, nmatches(concat_fields(item), request)) for item in list_of_objs]
    nmatches_distances = [item for item in nmatches_distances if item[1] > 0]
    nmatches_results = sorted(nmatches_distances, key=lambda x: x[1], reverse=True)
    nmatches_results = [x[0] for x in nmatches_results]
    nmatches_results = nmatches_results[:3]

    difflib_distances = [(item, difflib.SequenceMatcher(None, concat_fields(item), request).ratio()) for item in
                         list_of_objs]
    difflib_results = sorted(difflib_distances, key=lambda x: x[1], reverse=True)
    difflib_results = [x[0] for x in difflib_results]
    difflib_results = difflib_results[:3]

    complete_results = nmatches_results + difflib_results
    reduced_results = []
    for d in complete_results:
        new_obj = {}
        for key in always_keep:
            new_obj[key] = d[key]
        for key in d.keys():
            v = str(d[key])
            if v and set(re.split(separators, request.lower())) & set(re.split(separators, v.lower())):
                new_obj[key] = d[key]
        reduced_results.append(new_obj)
    return reduced_results


def post_process_fts(result, request, always_keep):
    r = []
    split_request = re.split(separators, request.lower())
    for d in result:
        new_obj = {}
        for key in always_keep:
            new_obj[key] = d[key]
        for key in d.keys():
            v = str(d[key])
            matches = [x for x in split_request if v.lower().find(x) != -1]
            if len(matches) > 0:
                new_obj[key] = d[key]
        r.append(new_obj)
    return r


def list_tvshows():
    sql = sqlite3.connect(db_file)
    cur = sql.cursor()
    sqlres = cur.execute(
        "SELECT _id, name_show, plot_show, rating_show, s_actors, s_directors, s_genres, s_writers FROM show")
    sqlres2 = sqlres.fetchall()
    r = []
    for (i, name, plot, rating, actors, directors, genres, writers) in sqlres2:
        r.append({'id': randomize_tvshowid(i), 'name': name})

    return r


def tvshow_search(request, depth = 0):
    sql = sqlite3.connect(db_file)
    cur = sql.cursor()
    request = re.sub('[^0-9a-zA-Z]+', ' ', request)
    sqlres = cur.execute(
        "SELECT _id FROM show_fts WHERE show_fts MATCH ? LIMIT 10", (request,))
    sqlres2 = sqlres.fetchall()
    query = "SELECT _id, name_show, plot_show, rating_show, s_actors, s_directors, s_genres, s_writers FROM show WHERE _id IN ("\
            + ",".join([str(x[0]) for x in sqlres2]) + ");"
    sqlres = cur.execute(query)
    sqlres2 = sqlres.fetchall()

    r = []
    for (i, name, plot, rating, actors, directors, genres, writers) in sqlres2:
        r.append({'id': randomize_tvshowid(i), 'name': name, 'plot': plot, 'rating': rating, 'actors': actors,
                  'directors': directors,
                  'genres': genres, 'writers': writers})
    if len(r) == 0 and depth == 0:
        # Try again by splitting request and searching for each word deleted
        split_request = re.split(separators, request)
        if len(split_request) <= 1:
            return {}

        list_of_founds_shows = {}
        for word in split_request:
            thisrequest = set(split_request) - {word}
            tmp = tvshow_search(" ".join(thisrequest), depth = depth + 1)
            for x in tmp:
                list_of_founds_shows[x['id']] = x
        r = list(list_of_founds_shows.values())
        return r

    return post_process_fts(r, request, ['id', 'name'])


def episodes_in_season(tvshow_id, season_id, give_plot=True):
    tvshow_id = unrandomize_tvshowid(tvshow_id)
    sql = sqlite3.connect(db_file)
    cur = sql.cursor()
    sqlres = cur.execute(f"SELECT e_episode, e_plot FROM video WHERE s_id = {tvshow_id} AND e_season = {season_id};")
    sqlres2 = sqlres.fetchall()
    r = []
    for (episode, plot) in sqlres2:
        if give_plot:
            r.append({'episode': episode, 'plot': plot})
        else:
            r.append({'episode': episode})
    return r


def list_episodes(tvshow_id):
    tvshow_id = unrandomize_tvshowid(tvshow_id)
    sql = sqlite3.connect(db_file)
    cur = sql.cursor()
    sqlres = cur.execute(f"SELECT e_season, e_episode, e_plot FROM video WHERE s_id = {tvshow_id};")
    sqlres2 = sqlres.fetchall()
    r = []
    for (season, episode, plot) in sqlres2:
        r.append({'season': season, 'episode': episode, 'plot': plot})
    return r


def seasons_in_tvshow(tvshow_id):
    tvshow_id = unrandomize_tvshowid(tvshow_id)
    sql = sqlite3.connect(db_file)
    cur = sql.cursor()
    sqlres = cur.execute(
        f"SELECT e_season, COUNT(*) AS episode_count FROM video WHERE s_id = {tvshow_id} GROUP BY e_season ORDER BY e_season ")
    sqlres2 = sqlres.fetchall()
    r = []
    for (s, n) in sqlres2:
        r.append({'season': s, 'n_episodes': n})
    return r


def search_in_tvshow(tvshow_id, match):
    if not check_tvshowid(tvshow_id):
        tvshow_id = unrandomize_tvshowid(tvshow_id)
        if not check_tvshowid(tvshow_id):
            return "No TVShow with this tvshow_id."
    sql = sqlite3.connect(db_file)
    match = re.sub('[^0-9a-zA-Z]+', ' ', match)
    cur = sql.cursor()
    # TODO: Add air time
    sqlres = cur.execute(
        f"SELECT _id FROM video_fts WHERE s_id = {tvshow_id} AND video_fts MATCH ? LIMIT 5;", (match,))
    sqlres2 = sqlres.fetchall()

    query = "SELECT e_season, e_episode, e_name, e_plot, e_actors, e_directors, e_writers FROM video WHERE _id IN ("\
            + ",".join([str(x[0]) for x in sqlres2]) + ") ORDER BY e_season ASC, e_episode ASC;"
    sqlres = cur.execute(query)
    sqlres2 = sqlres.fetchall()


    r = []
    for (season, episode, title, plot, actors, directors, writers) in sqlres2:
        d = {'season': season, 'episode': episode, 'title': title, 'plot': plot, 'actors': actors,
             'directors': directors, 'writers': writers}
        r.append(d)
    return post_process_fts(r, match, ['season', 'episode', 'title'])


def search_in_tvshow_season(tvshow_id, season, match):
    tvshow_id = unrandomize_tvshowid(tvshow_id)
    sql = sqlite3.connect(db_file)
    cur = sql.cursor()
    sqlres = cur.execute(
        f"SELECT _id FROM video_fts WHERE s_id = {tvshow_id} AND e_season = {season} AND video_fts MATCH ?;", (match,))
    sqlres2 = sqlres.fetchall()

    query = "SELECT e_season, e_episode, e_name, e_plot, e_actors, e_directors, e_writers FROM video WHERE _id IN ("\
            + ",".join([str(x[0]) for x in sqlres2]) + ") ORDER BY e_episode ASC;"
    sqlres = cur.execute(query)
    sqlres2 = sqlres.fetchall()

    r = []
    for (episode, title, plot) in sqlres2:
        d = {'episode': episode, 'title': title, 'plot': plot}
        # Yes this is rather ugly
        if match.lower() in json.dumps(d).lower():
            r.append(d)
    if len(r) == 0:
        return "No match found."
    return r


def tvshow_episode_info(tvshow_id, season_id, episode_id):
    tvshow_id = unrandomize_tvshowid(tvshow_id)
    sql = sqlite3.connect(db_file)
    cur = sql.cursor()
    request = f"SELECT e_id, e_plot, e_actors, e_directors, e_writers FROM video WHERE s_id = {tvshow_id} AND e_season = {season_id} AND e_episode = {episode_id};"
    print(request)
    sqlres = cur.execute(request)
    sqlres2 = sqlres.fetchone()
    if not sqlres2:
        return "No match found."
    (id, plot, actors, directors, writers) = sqlres2
    r = {'id': id, 'plot': plot, 'actors': actors, 'directors': directors}
    print(r)
    return r


def get_user_next_episode_for_tvshow(tvshow_id):
    # Our current test database don't have real information about the user, so we'll just return a random episode
    # Note: no unrandomize_tvshowid here, as it's already done by seasons_in_tvshow
    seasons = seasons_in_tvshow(tvshow_id)
    season = random.choice(seasons)['season']
    episodes = episodes_in_season(tvshow_id, season)
    episode = random.choice(episodes)['episode']
    return {'season': season, 'episode': episode}


def check_tvshowid(tvshow_id):
    sql = sqlite3.connect(db_file)
    cur = sql.cursor()
    request = f"SELECT COUNT(*) FROM video WHERE s_id = {tvshow_id};"
    sqlres = cur.execute(request)
    sqlres2 = sqlres.fetchone()
    if sqlres2[0] == 0:
        return False
    return True


finished = False

chosen_file = ""


def episode_play(tvshow_id, season_id, episode_id):
    global finished
    global chosen_file
    try:
        tvshow_id = unrandomize_tvshowid(tvshow_id)
        print(F"Playing episode {tvshow_id} {season_id} {episode_id}")
        if not check_tvshowid(tvshow_id):
            return "No TVShow with this tvshow_id."

        sql = sqlite3.connect(db_file)
        cur = sql.cursor()
        request = f"SELECT _data FROM video WHERE s_id = {tvshow_id} AND e_season = {season_id} AND e_episode = {episode_id};"
        print(request)
        sqlres = cur.execute(request)
        sqlres2 = sqlres.fetchone()
        uri = sqlres2[0]
        parts = uri.split('/')

        chosen_file = '/'.join(parts[4:])
        filepath = '/home/phh/d/d/d2/' + '/'.join(parts[4:])
        print("Playing", filepath)
        finished = True
        return "Playing episode"
    except Exception as e:
        traceback.print_exc(e)
        print("Tried to play a non-existing file", e)
        return "This episode is not available."


discussion = ""


def llamacpp_complete(txt):
    data = {
        'stream': False,
        'prompt': prompt,
        'n_predict': 2000,
        'grammar': grammar,
        'temperature': 0.35,
        'top_k': 40,
        'top_p': 0.95,
        'min_p': 0.05,
        'typical_p': 1,
    }

    headers = {'Content-Type': 'application/json'}
    data['prompt'] = prompt + txt
    response = requests.post(url, data=json.dumps(data), headers=headers)
    return json.loads(response.text)['content']


def mistral_complete(txt):
    data = {
        'messages': [
            {"role": "system", "content": prompt},
            {"role": "user", "content": txt},
        ],
        'model': 'mistral-medium'
    }

    headers = {'Content-Type': 'application/json', 'Authorization': "Bearer " + MistralAPI}
    response = requests.post('https://api.mistral.ai/v1/chat/completions', data=json.dumps(data), headers=headers)
    return json.loads(response.text)['choices'][0]['message']['content']


def togetherxyz_complete(txt):
    data = {
        'model': 'meta-llama/Llama-3-70b-chat-hf',
        #'model': 'meta-llama/Llama-3-8b-chat-hf',
        #'model': 'mistralai/Mixtral-8x22B-Instruct-v0.1',
        #'model': 'mistralai/Mixtral-8x22B',
        #'model': 'mistralai/Mixtral-8x7B-Instruct-v0.1',
        #'model': 'mistralai/Mistral-7B-Instruct-v0.2',
        # 'model': 'meta-llama/Llama-2-70b-chat-hf',
        # 'model': 'meta-llama/Llama-2-70b-hf',
        # 'model': 'google/gemma-7b-it',
        # 'model': 'microsoft/phi-2',
        'max_tokens': 512,
        'stream_tokens': False,
        "stop": ["</s>", "[/INST]"],
        'temperature': 0.35,
    }

    headers = {'Content-Type': 'application/json', "Authorization": "Bearer " + TogetherXYZ}
    data['prompt'] = prompt + txt
    response = requests.post('https://api.together.xyz/inference', data=json.dumps(data), headers=headers)
    if response.status_code != 200:
        print("Failed infering", response.text)
        return "Error"
    # Wait one second after the request to avoid being rate limited
    time.sleep(1)
    # print(response.text)
    return json.loads(response.text)['output']['choices'][0]['text']


# Create a function that continues the request and make "prompt" bigger to retain context
def continue_prompt():
    global discussion
    #content = llamacpp_complete(discussion)
    #content = mistral_complete(discussion)
    content = togetherxyz_complete(discussion)
    # print(content)
    okay_lines = [line for line in content.split("\n") if
                  line.startswith('Assistant:') or line.startswith('Thoughts:')]
    return okay_lines


if len(sys.argv) > 1:
    if sys.argv[1] == "search_tvshow":
        print(json.dumps(tvshow_search(sys.argv[2])))
        sys.exit(0)
    if sys.argv[1] == "search_episode_in_tvshow":
        print(json.dumps(search_in_tvshow(int(sys.argv[2]), sys.argv[3])))
        sys.exit(0)
    if sys.argv[1] == "ask":
        discussion += f"User: {sys.argv[2]}\n"
    if sys.argv[1] == "ask2":
        db_file = 'org.courville.nova-media.db'
        discussion += f"User: {sys.argv[2]}\n"

if len(discussion) == 0:
    discussion += "User: watch the artificial intelligence against nun\n"
lines = []
lines += continue_prompt()
while True:
    answer = None
    nextCall = None
    while len(lines) > 0:
        line = lines.pop(0)
        print("RX: " + line)
        discussion += line + "\n"
        if line.startswith("Assistant:"):
            l = line[len("Assistant:"):]
            # Sometimes the APIs send the final </s> tag, sometimes they don't
            # Remove it if it does
            if l.endswith("</s>"):
                print("Removing leading </s>")
                l = l[:-4]
            nextCall = json.loads(l)
            lines = []
            break
    if nextCall is None:
        print("----- Failed")
        print(discussion)
        print("----- Failed")
        sys.exit(1)

    function = nextCall['function']
    print(f"Calling function {function} {nextCall}")
    if function == 'search_tvshow' or function == 'search_tvshow':
        answer = tvshow_search(nextCall['query'])
    elif function == 'list_tvshows':
        answer = list_tvshows()
    elif function == 'list_seasons_in_tvshow':
        answer = seasons_in_tvshow(nextCall['tvshow_id'])
    elif function == 'list_episodes_in_season':
        answer = episodes_in_season(nextCall['tvshow_id'], nextCall['season'])
    elif function == 'list_episodes':
        answer = list_episodes(nextCall['tvshow_id'])
    elif function == 'get_tvshow_details':
        print("TO BE IMPLEMENTED")
        sys.exit(0)
    elif function == 'say':
        print(f"Assistant says {nextCall['message']}")
    elif function == 'play_episode':
        answer = episode_play(nextCall['tvshow_id'], nextCall['season'], nextCall['episode'])
        print(f"Playing episode {nextCall['tvshow_id']} {nextCall['season']} {nextCall['episode']}")
    elif function == 'get_episodes_infos':
        answer = tvshow_episode_info(nextCall['tvshow_id'], nextCall['season'], nextCall['episode'])
    elif function == 'search_episode_in_season':
        answer = search_in_tvshow_season(nextCall['tvshow_id'], nextCall['season'], nextCall['query'])
    elif function == 'search_episode_in_tvshow':
        answer = search_in_tvshow(nextCall['tvshow_id'], nextCall['query'])
    elif function == 'get_user_next_episode_for_tvshow':
        answer = get_user_next_episode_for_tvshow(nextCall['tvshow_id'])
        print("User next episode", answer)
    elif function == 'continue_tvshow':
        a = get_user_next_episode_for_tvshow(nextCall['tvshow_id'])
        answer = episode_play(nextCall['tvshow_id'], a['season'], a['episode'])
        print(f"Playing episode {nextCall['tvshow_id']} {a['season']} {a['episode']}")
    elif function == 'play_latest_episode':
        # Get the list of seasons
        seasons = seasons_in_tvshow(nextCall['tvshow_id'])

        # Get the last season
        last_season = max(seasons, key=lambda x: x['season'])
        # Get the list of episodes in the last season
        episodes = episodes_in_season(nextCall['tvshow_id'], last_season['season'])
        # Get the last episode
        last_episode = max(episodes, key=lambda x: x['episode'])
        # Play the last episode
        answer = episode_play(nextCall['tvshow_id'], last_season['season'], last_episode['episode'])
    elif function == 'end':
        finished = True
    else:
        exception = f"Function {function} not implemented"
        print(exception)
        print(discussion)
        sys.exit(1)
    if answer is not None:
        print("TX:" + json.dumps(answer))
        discussion += f"\nSystem: {json.dumps(answer)}\n"

    # If there are no more commands, call continue_prompt to get new ones
    if len(lines) == 0 and not finished:
        lines += continue_prompt()
    if finished:
        break

# Dump the content of the discussion inside dataset/timestamp.txt
with open(f"dataset/{int(time.time())}.txt", "w") as f:
    f.write(chosen_file + "\n")
    f.write("-------------" + "\n")
    f.write(discussion)
print("--------------------------------")
print(discussion)
