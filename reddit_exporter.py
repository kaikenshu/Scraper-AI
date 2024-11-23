import os
import pandas as pd
import praw
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Retrieve the MongoDB URI from environment variables
uri = os.getenv('MONGODB_URI')

if not uri:
    raise ValueError("MONGODB_URI is not set in the environment variables.")

# MongoDB setup
client = MongoClient(uri, server_api=ServerApi('1'))
db = client['news']
collection = db['reddit_raw']

# List of subreddits to scrape
subreddits = [
    'Bitcoin',
    'dogecoin',
    # 'MachineLearning',
    # 'Artificial',
    # 'TechNews',
    # 'Economics',
    # 'FinancialNews',
    # 'Finance',
    # 'Business',
    # 'StockMarket',
    # 'WallStreetBets',
]


# Create a function to flatten comments
def flatten_comments(comments):
    return " | ".join([
        f"{comment.get('Comment', 'No Comment')} (Likes: {comment.get('Comment_Score', 0)})"
        for comment in comments
    ])


# Loop through each subreddit
for subreddit in subreddits:
    # Fetch documents for the current subreddit
    documents = list(collection.find({'Subreddit': subreddit}))

    if not documents:
        print(f"No data found for subreddit: {subreddit}")
        continue

    # Flatten the data and prepare for CSV export
    flattened_data = []
    for doc in documents:
        flattened_doc = {
            'Created On': doc.get('Created On'),
            'Title': doc.get('Title'),
            'Score': doc.get('Score'),
            'Text': doc.get('Text'),
            'Comments': flatten_comments(doc.get('Comments', [])),  # Flatten the comments
            'URL': doc.get('URL')
        }
        flattened_data.append(flattened_doc)

    # Convert to a DataFrame
    df = pd.DataFrame(flattened_data)

    # Export to CSV using subreddit name
    filename = f"{subreddit}.csv"
    df.to_csv(filename, index=False)
    print(f"Data for {subreddit} exported successfully to {filename}!")
