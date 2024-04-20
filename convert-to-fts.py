#!/usr/bin/env python3
import os
import sqlite3
import sys


f1 = 'media.db'
f2 = 'media2.db'
# Remove media2.db if it exists
# And copy media.db to media2.db
try:
    os.remove(f2)
except:
    pass
try:
    os.system(f"cp {f1} {f2}")
except:
    sys.exit(1)


sql = sqlite3.connect(f2)

cur = sql.cursor()
fields = [
    '_id',
    # show fields
    's_id', 'actors', 's_plot', 's_writers', 's_directors', 's_name', 's_actors',
    # episode fields
    'e_season', 'e_episode', 'e_plot', 'e_actors', 'e_writers', 'e_directors', 'e_name',
]
request = "CREATE VIRTUAL TABLE video_fts USING fts5(" + ", ".join(fields) + ", tokenize='trigram');"
print(request)
cur.execute(request)
request = "INSERT INTO video_fts(" + ", ".join(fields) + ") SELECT " + ", ".join(fields) + " FROM video;"
print(request)
cur.execute(request)
sql.commit()

cur = sql.cursor()
fields = [
    # show fields
    '_id', 'name_show', 'plot_show', 's_actors', 's_directors', 's_genres', 's_studios', 's_writers'
]
request = "CREATE VIRTUAL TABLE show_fts USING fts5(" + ", ".join(fields) + ", tokenize='trigram');"
print(request)
cur.execute(request)
request = "INSERT INTO show_fts(" + ", ".join(fields) + ") SELECT " + ", ".join(fields) + " FROM show;"
print(request)
cur.execute(request)
sql.commit()

sql.close()
