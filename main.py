import functions_framework
import os
import requests
import pandas as pd
import feedparser
import numpy as np
from google.cloud import bigquery
from pandas_gbq import to_gbq
from pandas_gbq import read_gbq
import shutil
#from pydub import AudioSegment


def download_file(url, filename):
    response = requests.get(url, stream=True)
    response.raise_for_status()
    with open(filename, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)

def ingest_podcast_rss(url):
    response = requests.get(url)
    response.raise_for_status()
    feed = feedparser.parse(response.content)

    episode_ids = []
    titles = []
    tags = []
    summaries = []
    published_dates = []

    # Read to dataframe
    prev_episodes_df = read_gbq(
        "SELECT * FROM `podcast_metadata.locked_on_bills_episode_metadata`",
        project_id="my-project-1539713919463"
    )

    entries_df = pd.DataFrame(feed.entries)
    entries_df = entries_df[
        ~(entries_df['title'].str.startswith('NFL Squad') |
          entries_df['title'].str.startswith('BILLS SQUAD') |
          entries_df['title'].str.startswith('NFL SQUAD') |
          entries_df['title'].str.startswith('NFL Mock Draft')) &
        entries_df['links'].notna()
    ]
    entries_df = entries_df[~entries_df['id'].isin(set(prev_episodes_df['episode_id']))]

    entry = entries_df.iloc[0]
    episode_id = entry.id
    title = entry.title
    published_time = entry['published_parsed']
    published_date = f"{published_time.tm_mon}/{published_time.tm_mday}/{published_time.tm_year}"
    print("Date:", published_date)
    print("Title:", title)

    for link in entry.links:
        if link.type == 'audio/mpeg':
            file_path = os.path.join("mp3-files", entry.id + ".mp3")
            print("Downloading:", file_path)
            download_file(link.href, file_path)

    print("---------")
    episode_ids.append(episode_id)
    titles.append(title)
    summaries.append(entry.summary)
    published_dates.append(published_date)

    try:
        if 'tags' in entry:
            tags.append(', '.join([tag['term'] for tag in entry.tags]))
        else:
            tags.append(None)
    except:
        tags.append(None)

    return pd.DataFrame({
        'episode_id': episode_ids,
        'published_date': published_dates,
        'title': titles,
        'summary': summaries,
        'tags': tags
    })

def split_m4a(mp3_file_folder, mp3_chunk_folder, episode_id, chunk_length_ms, overlap_ms, print_output):
    # Load the audio file
    audio = AudioSegment.from_file(mp3_file_folder + "/" + episode_id + ".mp3", format="mp3")
    
    # Calculate the number of chunks
    num_chunks = len(audio) // (chunk_length_ms - overlap_ms) + (1 if len(audio) % chunk_length_ms else 0)
    
    # Split the file into chunks
    for i in range(num_chunks):
        start_ms = i * chunk_length_ms - (i * overlap_ms)
        end_ms = start_ms + chunk_length_ms
        chunk = audio[start_ms:end_ms]
        
        # Export each chunk to a file
        export_fp = mp3_chunk_folder + "/" + episode_id + f"_chunk{i+1}.mp3"
        chunk.export(export_fp, format="mp3")
        if print_output:
            print('Exporting', export_fp)
        
    return chunk 

@functions_framework.cloud_event
def run(cloud_event):
    os.makedirs("mp3-files", exist_ok=True)
    os.makedirs("mp3-chunks", exist_ok=True)

    try:
        url = 'https://feeds.simplecast.com/LIaoLB9Y'
        episode_metadata_df = ingest_podcast_rss(url)
        episode_metadata_df['published_date'] = pd.to_datetime(episode_metadata_df['published_date'], errors='coerce').dt.strftime('%Y-%m-%d')

        to_gbq(
            episode_metadata_df,
            'podcast_metadata.locked_on_bills_episode_metadata',
            project_id='my-project-1539713919463',
            if_exists='append'
        )

        mp3_file_folder = "mp3-files"
        mp3_chunk_folder = "mp3-chunks"
        chunk_length_ms=500000 # Split into 1000s chunks (16.67 min)
        overlap_ms=10000 # 10s overlap between chunks

        print_output = True
        for fil in os.listdir(mp3_file_folder):
            episode_id = fil.split('.')[0]
            print('Splitting Episode ID:', episode_id)
            #chunk = split_m4a(mp3_file_folder, mp3_chunk_folder, episode_id, chunk_length_ms, overlap_ms, print_output)
            print_output = False

    except Exception as e:
        print(f"Error occurred: {str(e)}")
        # DO NOT raise — just log and exit gracefully

    finally:
        shutil.rmtree("mp3-files", ignore_errors=True)
        shutil.rmtree("mp3-chunks", ignore_errors=True)
