#!/usr/bin/env python3
import difflib
import sqlite3
import sys
import time

import requests
import json

url = 'http://192.168.1.82:8080/completion'

prompt = """
You are a helpful assistant to 'User'. You do not respond as 'User' or pretend to be 'User'. You only respond once as 'Assistant'. 'System' will give you data. Do not respond as 'System'. Always explain why you do what you do with lines starting with 'Thoughts:'.
You control a tvbox. You have the list of tv shows available, and can browse the full catalogue. Prefer recent content. Your role is to chose which file matches the user's request and play it with a very short answer, using JSON commands.
Finish every command with </s>

Available functions are:
- list_tvshows: List of TV Shows in the database. Example: {"function":"list_tvshows"}</s> returns [{"id":4, "name":"Doctor who"}]
- search_tvshows: Search for a TV Series (not episodes) by anything, name, plot, genre, actors. Example: {"function":"search_tvshow","query":"doctor sci-fi"}</s> returns [{"id":31,"name":"Doctor Who","genres":"sci-fi"},{"id":42,"name":"Condor"},{"id":32,"name":"Doctor Who 1963"},{"id":39,"name":"Industry"},{"id":11,"name":"Sex Education"}]
- list_seasons_in_tvshow: Get the list of seasons within a TV show, including the number of episodes in the season. Example: {"function":"list_seasons_in_tvshow", "tvshow_id":4}</s> returns [{"s":1", n":10}]
- list_episodes_in_season: Get the list of episodes with description within a TV show season. Example: {"function":"list_episodes_in_season", "tvshow_id":4,"season":1}</s> returns {"episode":1, "name":"Rose","plot":"When ordinary shop-worker Rose Tyler meets a mysterious stranger called the Doctor she is drawn into his strange and dangerous world; her life will never be the same again."}
- get_episodes_infos: Get more informations about a TV show episode, including actors, directors and writers: {"function":"get_episodes_infos", "tvshow_id":4, "season":1, "episode":1}</s> returns {"plot":"We discover rose", "actors": "Billie Piper, Christopher Eccleston", "writers": "Russell T. Davies"}
- search_episode_in_season: Search for an episode in a season. Example: {"function":"search_in_tvshow_season", "tvshow_id":4,"season":1,"match":"jail"}</s> returns {"episode":1,"plot":"Rose goes to jail"}
- search_episode_in_tvshow: Search for an episode in a season. Example: {"function":"search_in_tvshow", "tvshow_id":4,"match":"jail"}</s> returns {"season":1,"episode":1,"plot":"Rose goes to jail"}
- play_episode: Launch the playback of an episode. Example: {"function":"play_episode","tvshow_id":4,"season":1,"episode":1}</s>
- say: Answer to the user {"function":"say","message":"Here is that awesome Moffat episode"}</s>

Here is an example on how to answer the user's request:
User: Watch the latest Last Week Tonight
Thoughts: I search for user's "Last Week Tonight" tvshow
Assistant: {"function":"search_tvshow","query":"last week tonight"}</s>
System: [{"id":74,"name":"Last Week Tonight with John Oliver"},{"id":8,"name":"Batwoman"},{"id":48,"name":"Black Mirror"},{"id":29,"name":"His Dark Materials"},{"id":66,"name":"Bonding"}]
Thoughts: Okay, the closest TV Show seems to be the one with id 3, let's list its seasons.
Assistant: {"function":"list_seasons_in_tvshow","tvshow_id":3}</s>
System: [{"s":1,"n":4},{"s":2,"n":6}]
Thoughts: Most recent season is Season 2, let's list its episodes.
Assistant: {"function":"list_episodes_in_season","tvshow_id":3,"season":2}</s>
System: [{"episode":1,"name":"Episode 1","plot":"This is the plot of the first episode"},{"episode":2,"name":"Episode 2","plot":"This is the plot of the second episode"}]
Thoughts: This must be the one with the highest number, season 2 episode 2. Let's play it
Thoughts: And say something nice to the user
Assistant: {"function":"say","message": "Enjoy that episode!"}</s>
Assistant: {"function":"play_episode","tvshow_id":4,"season":2,"episode":5}</s>

Another example:
User: Watch Scrubs S1E3
Thoughts: I search for user's "scrubs" tvshow
Assistant: {"function":"search_tvshow","query":"scrubs"}</s>
System: [{"id":5,"name":"Scrubs"},{"id":28,"name":"Mythic Quest"},{"id":46,"name":"Most Dangerous Game"},{"id":25,"name":"Trust Me 2017"},{"id":39,"name":"Industry"}]
Thoughts: Okay, the closest TV Show seems to be the one with id 5, let's list its seasons.
Assistant: {"function":"list_seasons_in_tvshow","tvshow_id":5}</s>
System: [{"s":1,"n":2},{"s":2,"n":2}]
Thoughts: Okay the season 1 the user want exists, let's list its episodes.
Assistant: {"function":"list_episodes_in_season","tvshow_id":5,"season":1}</s>
System: [{"episode":8,"plot":"J.D. and Turk become heroes after [...]"},{"episode":6,"plot":"Dr. Cox is still facing the [...]"},{"episode":11,"plot":"It's Christmas, and even though J.D. and t[...]"}]
Thoughts: Okay, user requested season 1 episode 3, and it's there! Let's play it
Assistant: {"function":"play_episode","tvshow_id":5,"season":1,"episode":3}</s>

Never suppose your knowledge is up-to-date, always do database requests to confirm.
Stop on the first request, do not continue the conversation.

"""

grammar = '''
root   ::= innerThought cmd-line

innerThought ::= "Thoughts: " [^\\n]* "\\n"
cmd-line ::= "Assistant: " cmd "\\n"

space ::= " "?
0-function ::= "\\"list_tvshows\\""
0 ::= "{" space "\\"function\\"" space ":" space 0-function "}" space
1-function ::= "\\"search_tvshow\\""
string ::=  "\\"" (
        [^"\\\\] |
        "\\\\" (["\\\\/bfnrt] | "u" [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F])
      )* "\\"" space
1 ::= "{" space "\\"function\\"" space ":" space 1-function "," space "\\"query\\"" space ":" space string "}" space
2-function ::= "\\"list_seasons_in_tvshow\\""
integer ::= ("-"? ([0-9] | [1-9] [0-9]*)) space
2 ::= "{" space "\\"function\\"" space ":" space 2-function "," space "\\"tvshow_id\\"" space ":" space integer "}" space
3-function ::= "\\"list_episodes_in_season\\""
3 ::= "{" space "\\"function\\"" space ":" space 3-function "," space "\\"tvshow_id\\"" space ":" space integer "," space "\\"season\\"" space ":" space integer"}" space
4-function ::= "\\"get_episodes_infos\\""
4 ::= "{" space "\\"function\\"" space ":" space 4-function ","  space "\\"tvshow_id\\"" space ":" space integer  ","  space "\\"season\\"" space ":" space integer "," space "\\"episode\\"" space ":" space integer  "}" space
5-function ::= "\\"play_episode\\""
5 ::= "{" space "\\"function\\"" space ":" space 5-function "," space "\\"tvshow_id\\"" space ":" space integer  "," space "\\"season\\"" space ":" space integer "," space "\\"episode\\"" space ":" space integer "}" space
6-function ::= "\\"say\\""
6 ::= "{" space "\\"function\\"" space ":" space 6-function "," space "\\"message\\"" space ":" space string "}" space
cmd ::= 0 | 1 | 2 | 3 | 4 | 5 | 6
'''

def nmatches(s1, s2):
    # TODO: lemmizer?
    # TODO: remove stopwords
    # TODO: remove punctuation
    # TODO: remove accents
    # TODO: remove plurals
    return len(set(s1.lower().split(" ")) & set(s2.lower().split(" ")))

def tvshow_search(request):
    sql = sqlite3.connect('media.db')
    cur = sql.cursor()
    sqlres = cur.execute("SELECT _id, name_show, plot_show, rating_show, s_actors, s_directors, s_genres, s_writers FROM show")
    sqlres2 = sqlres.fetchall()
    r = []
    for (i, name, plot, rating, actors, directors, genres, writers) in sqlres2:
        r.append({'id': i, 'name': name, 'plot': plot, 'rating': rating, 'actors': actors, 'directors': directors,
                  'genres': genres, 'writers': writers})

    # Calculate Levenshtein distance for each item in data
    #distances = [(item, difflib.SequenceMatcher(None, json.dumps(item), request).ratio()) for item in r]
    distances = [(item, nmatches(json.dumps(item), request)) for item in r]
    distances = [item for item in distances if item[1] > 0]

    distances += [(item, difflib.SequenceMatcher(None, json.dumps(item), request).ratio()) for item in r]


    # Sort by Levenshtein distance
    sorted_results = sorted(distances, key=lambda x: x[1], reverse=True)

    # Extract the dictionaries from the sorted list
    sorted_dicts = [item[0] for item in sorted_results]
    restricted_dicts = sorted_dicts[:5]
    # Filter out the useful fields
    r = []
    for d in restricted_dicts:
        d2 = {'id': d['id'], 'name': d['name'], 'rating': d['rating'], 'genres': d['genres']}
        # Copy the key if it might be relevant to the match
        for key in ['plot', 'actors', 'directors', 'writers']:
            if d[key] and set(request.lower().split(" ")) & set(d[key].lower().split(" ")):
                d2[key] = d[key]

        r.append(d2)

    return r


def episodes_in_season(tvshow_id, season_id):
    sql = sqlite3.connect('media.db')
    cur = sql.cursor()
    sqlres = cur.execute(f"SELECT e_episode, e_plot FROM video WHERE s_id = {tvshow_id} AND e_season = {season_id};")
    sqlres2 = sqlres.fetchall()
    r = []
    for (episode, plot) in sqlres2:
        r.append({'episode': episode, 'plot': plot})
        # r.append({'episode': episode})
    return r


def seasons_in_tvshow(tvshow_id):
    sql = sqlite3.connect('media.db')
    cur = sql.cursor()
    sqlres = cur.execute(
        f"SELECT e_season, COUNT(*) AS episode_count FROM video WHERE s_id = {tvshow_id} GROUP BY e_season ORDER BY e_season ")
    sqlres2 = sqlres.fetchall()
    r = []
    for (s, n) in sqlres2:
        r.append({'season': s, 'n_episodes': n})
    return r



def search_in_tvshow(tvshow_id, match):
    sql = sqlite3.connect('media.db')
    cur = sql.cursor()
    sqlres = cur.execute(
        f"SELECT e_episode, e_name, e_plot FROM video WHERE s_id = {tvshow_id};")
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

def search_in_tvshow_season(tvshow_id, season, match):
    sql = sqlite3.connect('media.db')
    cur = sql.cursor()
    sqlres = cur.execute(
        f"SELECT e_episode, e_name, e_plot FROM video WHERE s_id = {tvshow_id} AND e_season = {season};")
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
    sql = sqlite3.connect('media.db')
    cur = sql.cursor()
    request = f"SELECT e_id, e_plot, e_actors, e_directors, e_writers FROM video WHERE s_id = {tvshow_id} AND e_season = {season_id} AND e_episode = {episode_id};"
    print(request)
    sqlres = cur.execute(request)
    sqlres2 = sqlres.fetchone()
    (id, plot, actors, directors, writers) = sqlres2
    r = {'id': id, 'plot': plot, 'actors': actors, 'directors': directors}
    print(r)
    return r


finished = False


def episode_play(tvshow_id, season_id, episode_id):
    global finished
    try:
        print(F"Playing episode {tvshow_id} {season_id} {episode_id}")
        sql = sqlite3.connect('media.db')
        cur = sql.cursor()
        request = f"SELECT _data FROM video WHERE s_id = {tvshow_id} AND e_season = {season_id} AND e_episode = {episode_id};"
        sqlres = cur.execute(request)
        sqlres2 = sqlres.fetchone()
        uri = sqlres2[0]
        parts = uri.split('/')

        filepath = '/home/phh/d/d/d2/' + '/'.join(parts[4:])
        print("Playing", filepath)
        finished = True
    except:
        print("Tried to play a non-existing file")
        return "This episode is not available"


discussion = ""


def llamacpp_complete(txt):
    data = {
        'stream': False,
        'prompt': prompt,
        'n_predict': 2000,
        'grammar': grammar,
        'temperature': 0.75,
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
        'model': 'mistralai/Mixtral-8x7B-Instruct-v0.1',
        'max_tokens': 512,
        'stream_tokens': False,
        "stop": ["</s>", "[/INST]"],
        'temperature':0.1,
    }

    headers = {'Content-Type': 'application/json', "Authorization": "Bearer " + TogetherXYZ}
    data['prompt'] = prompt + txt
    response = requests.post('https://api.together.xyz/inference', data=json.dumps(data), headers=headers)
    if response.status_code != 200:
        print("Failed infering", response.text)
        return "Error"
    # Wait one second after the request to avoid being rate limited
    time.sleep(1)
    return json.loads(response.text)['output']['choices'][0]['text']


# Create a function that continues the request and make "prompt" bigger to retain context
def continue_prompt():
    global discussion
    # content = llamacpp_complete(discussion)
    # content = mistral_complete(discussion)
    content = togetherxyz_complete(discussion)
    okay_lines = [line for line in content.split("\n") if
                  line.startswith('Assistant:') or line.startswith('Thoughts:')]
    return okay_lines


discussion += "User: Watch the sci-fi soap opera with Hugh Laurie\n"
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
            nextCall = json.loads(line[len("Assistant:"):])
            lines = []
            break
    if nextCall is None:
        sys.exit(1)

    function = nextCall['function']
    print(f"Calling function {function} {nextCall}")
    if function == 'search_tvshow':
        answer = tvshow_search(nextCall['query'])
    elif function == 'list_seasons_in_tvshow':
        answer = seasons_in_tvshow(nextCall['tvshow_id'])
    elif function == 'list_episodes_in_season':
        answer = episodes_in_season(nextCall['tvshow_id'], nextCall['season'])
    elif function == 'say':
        print(f"Assistant says {nextCall['message']}")
    elif function == 'play_episode':
        answer = episode_play(nextCall['tvshow_id'], nextCall['season'], nextCall['episode'])
        print(f"Playing episode {nextCall['tvshow_id']} {nextCall['season']} {nextCall['episode']}")
    elif function == 'get_episodes_infos':
        answer = tvshow_episode_info(nextCall['tvshow_id'], nextCall['season'], nextCall['episode'])
    elif function == 'search_episode_in_season':
        answer = search_in_tvshow_season(nextCall['tvshow_id'], nextCall['season'], nextCall['match'])
    elif function == 'search_episode_in_tvshow':
        answer = search_in_tvshow(nextCall['tvshow_id'], nextCall['match'])
    else:
        exception = f"Function {function} not implemented"
        print(exception)
        print(discussion)
        sys.exit(0)
    if answer:
        discussion += f"\nSystem: {json.dumps(answer)}\n"

    # If there are no more commands, call continue_prompt to get new ones
    if len(lines) == 0 and not finished:
        lines += continue_prompt()
    if finished:
        break

# Dump the content of the discussion inside dataset/timestamp.txt
with open(f"dataset/{int(time.time())}.txt", "w") as f:
    f.write(discussion)
print("--------------------------------")
print(discussion)
