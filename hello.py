#!/usr/bin/env python3

from flask import Flask
from apiflask import APIFlask, Schema, PaginationSchema
from apiflask.fields import Integer, String, List, Nested
import sqlite3
import os
import difflib

app = APIFlask(__name__, spec_path='/openapi.yaml', title='NOVA Video Player remotr controller API')
app.servers = [{"name": "Hello", "url": "https://771bc29cf519dc.lhr.life"}]
app.config['SPEC_FORMAT'] = 'yaml'


class TvShow(Schema):
    id = Integer()
    name = String()


class EpisodeIdentifier(Schema):
    s = Integer()
    e = Integer()


class SeasonDescription(Schema):
    s = Integer()
    n = Integer()


class EpisodeLight(Schema):
    episode = Integer()
    plot = String()


class EpisodeInfos(Schema):
    id = Integer()
    plot = String()
    actors = String()
    directors = String()
    writers = String()


@app.get('/search/<string:request>')
@app.output(TvShow(many=True), status_code=200, description='List of TV Shows in the database')
@app.doc(operation_id="list_tvshows")
def tvshow_search(request):
    sql = sqlite3.connect('media.db')
    cur = sql.cursor()
    sqlres = cur.execute("SELECT _id, name_show FROM show")
    sqlres2 = sqlres.fetchall()
    r = []
    for (i, name) in sqlres2:
        r.append({'id': i, 'name': name})
    print("Request is", request)
    # Calculate Levenshtein distance for each item in data
    distances = [(item, difflib.SequenceMatcher(None, item['name'], request).ratio()) for item in r]

    # Sort by Levenshtein distance
    sorted_results = sorted(distances, key=lambda x: x[1], reverse=True)

    # Extract the dictionaries from the sorted list
    sorted_dicts = [item[0] for item in sorted_results]
    print(sorted_dicts[:5])
    return sorted_dicts[:5]


@app.get('/tvshow')
@app.output(TvShow(many=True), status_code=200, description='List of TV Shows in the database')
@app.doc(operation_id="list_tvshows")
def tvshow():
    sql = sqlite3.connect('media.db')
    cur = sql.cursor()
    sqlres = cur.execute("SELECT _id, name_show FROM show")
    sqlres2 = sqlres.fetchall()
    r = []
    for (i, name) in sqlres2:
        r.append({'id': i, 'name': name})
    return r


@app.get('/tvshow/<int:tvshow_id>')
@app.output(SeasonDescription(many=True), status_code=200, description='Get the list of seasons within a TV show')
@app.doc(operation_id="list_seasons_in_tvshow")
def tvshow_id(tvshow_id):
    sql = sqlite3.connect('media.db')
    cur = sql.cursor()
    sqlres = cur.execute(
        f"SELECT e_season, COUNT(*) AS episode_count FROM video WHERE s_id = {tvshow_id} GROUP BY e_season ORDER BY e_season ")
    sqlres2 = sqlres.fetchall()
    print(sqlres2)
    r = []
    for (s, n) in sqlres2:
        r.append({'s': s, 'n': n})
    print(r)
    return r


# @app.get('/tvshow/<int:tvshow_id>')
# @app.output(EpisodeIdentifier(many = True), status_code=200, description='Get the list of episodes within a TV show')
# @app.doc(operation_id="list_episodes_in_tvshow")
# def tvshow_id(tvshow_id):
#    sql = sqlite3.connect('media.db')
#    cur = sql.cursor()
#    sqlres = cur.execute(f"select e_season, e_episode from video where s_id = {tvshow_id};")
#    sqlres2 = sqlres.fetchall()
#    print(sqlres2)
#    r = []
#    for (s, e) in sqlres2:
#        r.append({'season': s, 'episode' : e})
#    print(r)
#    return r

@app.get('/tvshow/<int:tvshow_id>/episode/<int:season_id>')
@app.output(EpisodeLight(many=True), status_code=200, description='Get the plot of the episodes within a season')
@app.doc(operation_id="list_episodes_in_season")
def tvshows_in_season(tvshow_id, season_id):
    sql = sqlite3.connect('media.db')
    cur = sql.cursor()
    sqlres = cur.execute(f"SELECT e_episode, e_plot FROM video WHERE s_id = {tvshow_id} AND e_season = {season_id};")
    sqlres2 = sqlres.fetchall()
    print(sqlres2)
    r = []
    for (episode, plot) in sqlres2:
        r.append({'episode': episode, 'plot': plot})
    print(r)
    return r


@app.get('/tvshow/<int:tvshow_id>/episode/<int:season_id>/<int:episode_id>')
@app.doc(operation_id="get_episodes_infos")
@app.output(EpisodeInfos(), status_code=200,
            description='Get detailed information about a specific episode, including actors, directors and writers')
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


@app.post('/tvshow/<int:tvshow_id>/episode/<int:season_id>/<int:episode_id>/play')
@app.doc(operation_id="play_episode")
def episode_play(tvshow_id, season_id, episode_id):
    print(F"Playing episode {tvshow_id} {season_id} {episode_id}")
    sql = sqlite3.connect('media.db')
    cur = sql.cursor()
    request = f"SELECT _data FROM video WHERE s_id = {tvshow_id} AND e_season = {season_id} AND e_episode = {episode_id};"
    print(request)
    sqlres = cur.execute(request)
    sqlres2 = sqlres.fetchone()
    uri = sqlres2[0]
    parts = uri.split('/')

    filepath = '/home/phh/d/d/d2/' + '/'.join(parts[4:])
    os.system(f'mpv "{filepath}" &')
    print(f"Playing {sqlres2}")

    return "Success"


if __name__ == '__main__':
    app.run(debug=True, port=8080, host='::')
