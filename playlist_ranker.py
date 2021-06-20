# Created by Muzammil Siddiq
# On 20/06/2021 7:00 pm

# For scheduling this task on daily basis windows schedular could be used
# For linux cronjob could be used

from sklearn.preprocessing import MinMaxScaler
from datetime import datetime

import pandas as pd
import numpy as np
import requests
import time
import json

# Fetch promoter playlists from links.txt file
with open("links.txt", 'r') as fp:
    links = fp.read()

promoter_playlist_ids = [link.split('/')[-1] for link in links.split('\n')]

# Connection to API
client_id = "d0ddb71932df40e0b3a653a1b865b74f"
client_secret = "396a51bd90d14bcd842c4e0e8217a011"
auth_url = "https://accounts.spotify.com/api/token"
base = "https://api.spotify.com/v1/"
playlists = "playlists/"
rapcaviar_playlist_id = "37i9dQZF1DX0XUsuxWHRQd"

# Getting Access Token
auth_response = requests.post(auth_url, {
    'grant_type': 'client_credentials',
    'client_id': client_id,
    'client_secret': client_secret,
}).json()

access_token = auth_response['access_token']

headers = {
    'Authorization': 'Bearer {token}'.format(token=access_token)
}

response = requests.get('https://api.spotify.com/v1/playlists/37i9dQZF1DX0XUsuxWHRQd', headers=headers).json()

tracks_rc = {
    "id": [],
    "name": [],
    "added_at": [],
}

# DataFrame to fill info relevant info about RapCavier Playlist (in sorted order based on added_at)
# Sorting could be improved further (time complexity)
for item in response['tracks']['items']:
    tracks_rc['id'].append(item['track']['id'])
    tracks_rc['name'].append(item['track']['name'])
    tracks_rc['added_at'].append(datetime.fromisoformat(item['added_at'][:-1]))

    tracks_rc['added_at'], tracks_rc['name'], tracks_rc['id'] = list(map(list, zip(*sorted(zip( tracks_rc['added_at'],
                                                                                                tracks_rc['name'], 
                                                                                                tracks_rc['id'] )))))

df_rc = pd.DataFrame(tracks_rc)

# Stub dictionary that will be filled with the loop below
playlist_info = {
                    'name' : [],
                    'followers' : [],
                    'total_songs' : [],
                    'promoted_songs' : [],
                    'songs_promoted_ratio' : [],
                    'avg_promotion_time_hours' : [],
                }

# Process each Promoter Playlist and fetch required info to rank them. 
for playlist in promoter_playlist_ids:
    response = requests.get(base + playlists + playlist, headers=headers).json()

    tracks = {
        "id": [],
        "name": [],
        "added_at": [],
    }

    # Same sorting and fetching logic from RapCavier playlist
    total_songs = 0
    for item in response['tracks']['items']:
        if item['track']:
            total_songs += 1
            tracks['id'].append(item['track']['id'])
            tracks['name'].append(item['track']['name'])
            tracks['added_at'].append(datetime.fromisoformat(item['added_at'][:-1]))

            tracks['added_at'], tracks['name'], tracks['id'] = list(map(list, zip(*sorted(zip( tracks['added_at'],
                                                                                        tracks['name'], 
                                                                                        tracks['id'] )))))

    df = pd.DataFrame(tracks)

    # Compare and fetch the songs that are present in both dataframes
    # rapcavier playlist and promoter playlist that is in the iter
    df_c = df_rc[df_rc['added_at'] >= df['added_at'][0]]
    
    # Fetch only those songs that are present in both playlists (rc and P)
    filtered_df_rc = df_c[df_c.name.isin(df['name'])]

    # Reset index for further comparison
    filtered_df_rc.reset_index(drop=True, inplace=True)
    # Create a timestamp column from added_at datetime
    filtered_df_rc['ts'] = filtered_df_rc.added_at.values.astype(np.int64) // 10 ** 9

    # Same for promoter playlist so added_at value of both playlist can be fetched for comparison
    filtered_df_pl = df[df.name.isin(df_c['name'])]
    filtered_df_pl.reset_index(drop=True, inplace=True)
    filtered_df_pl['ts'] = filtered_df_pl.added_at.values.astype(np.int64) // 10 ** 9

    # Now datetime timestamp
    now_tc = datetime.timestamp(datetime.now())

    # Compare both added_at and fetch the songs that were first in the promoter playlist then transferred to RapCavier
    # Also difference (in hours) is calculated between the time when it was added in rc and till now
    filtered_df_rc['promotion_time_hours'] = np.where(  filtered_df_rc.ts >= filtered_df_pl.ts,
                                                            (now_tc - filtered_df_rc.ts) / (60 * 60),
                                                            0
                                                        )
                                                        
    # All the appropriate values are transferred to the dictionary
    playlist_info['name'].append(response['name'])
    playlist_info['followers'].append(response['followers']['total'])
    
    promoted_songs = len(filtered_df_rc[filtered_df_rc['promotion_time_hours'] > 0])
    playlist_info['total_songs'].append(total_songs) 
    playlist_info['promoted_songs'].append(promoted_songs)
    # Ratio is calculated for scalability
    playlist_info['songs_promoted_ratio'].append(promoted_songs / total_songs if total_songs else 0)
    
    # Average promotion time per playlist is calculated
    total_promotion_time_hours = sum(filtered_df_rc['promotion_time_hours'])
    playlist_info['avg_promotion_time_hours'].append(total_promotion_time_hours / promoted_songs if total_promotion_time_hours else 0)


playlist_df = pd.DataFrame(playlist_info)

# Normalization is used to rank the promoter playlists present in the dataframe
# Ranks will change as more promoter playlists are used
scaler = MinMaxScaler()
col = playlist_df.columns[1].split() + list(playlist_df.columns[4:])

scaled = scaler.fit_transform(playlist_df[col])
scaled_df = pd.DataFrame(scaled)
playlist_df['ranking'] = scaled_df[0] + scaled_df[1] + scaled_df[2]

# Ranked promoter playlists are stored in csv files
playlist_df.sort_values(by='ranking', ascending=False, inplace=True)
playlist_df.to_csv("ranked_playlists.csv")