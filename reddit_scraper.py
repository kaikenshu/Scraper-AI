import os
from datetime import datetime, timezone
from dotenv import load_dotenv
import praw
from openai import OpenAI
from praw.models import Comment
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from zoneinfo import ZoneInfo
import requests
from io import BytesIO
from PIL import Image, ImageFilter
import pytesseract
import openai

# **Load environment variables from .env file**
load_dotenv()

# **MongoDB Configuration**
MONGODB_URI = os.getenv("MONGODB_URI")

# **Reddit API Configuration**
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT")
REDDIT_USER_NAME = os.getenv("REDDIT_USER_NAME")
REDDIT_USER_PASSWORD = os.getenv("REDDIT_USER_PASSWORD")
GPT_API_KEY = os.getenv("GPT_API_KEY")

# **Initialize Reddit Instance**
reddit = praw.Reddit(
    client_id=REDDIT_CLIENT_ID,
    client_secret=REDDIT_CLIENT_SECRET,
    user_agent=REDDIT_USER_AGENT,
    username=REDDIT_USER_NAME,
    password=REDDIT_USER_PASSWORD
)

# **MongoDB Setup**
try:
    client = MongoClient(MONGODB_URI, server_api=ServerApi('1'))
    db = client['news']
    collection = db['reddit_raw']  # Changed to 'reddit_raw' without space for consistency
    print("MongoDB connection established successfully.")
except Exception as e:
    print(f"Error connecting to MongoDB: {e}")

#E **Ensure tesseract works**
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# **List of Subreddits to Scrape**
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

# **Function to Extract Text from Image URL**
def extract_text_from_image(url):
    try:
        print(f"Attempting to download image from URL: {url}")
        response = requests.get(url)
        response.raise_for_status()
        img = Image.open(BytesIO(response.content))
        print(f"Image downloaded successfully from {url}")

        # Optional: Preprocess the image for better OCR results
        img = img.convert('L')  # Convert to grayscale
        img = img.filter(ImageFilter.SHARPEN)  # Sharpen the image

        text = pytesseract.image_to_string(img, lang='eng')
        print(f"Extracted Text: {text.strip()}")
        return text.strip()
    except Exception as e:
        print(f"Error processing image from {url}: {e}")
        return ""

# **Function to Determine if a URL Points to an Image**
def is_image_url(url):
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp']
    return any(url.lower().endswith(ext) for ext in image_extensions)

# **Get Current Date and Time in PST Timezone**
now_pst = datetime.now(ZoneInfo("America/Los_Angeles"))
today_date = now_pst.strftime('%Y-%m-%d %H:%M:%S')

# **Main Scraping Loop**
for subreddit_name in subreddits:
    print(f"\nScraping subreddit: {subreddit_name}")
    subreddit = reddit.subreddit(subreddit_name)
    for submission in subreddit.hot(limit=200):
        # Calculate the time since the post was created
        post_creation_time = datetime.fromtimestamp(submission.created_utc, tz=timezone.utc)
        hours_since_posted = (datetime.now(timezone.utc) - post_creation_time).total_seconds() / 3600
        min_score = 30 * hours_since_posted

        # Skip articles that do not meet the score requirement
        if submission.score < min_score:
            print(f"Skipping post: {submission.title} (Score: {submission.score}, Minimum Required: {min_score})")
            continue

        # Determine if the post is a text post or an image post
        if submission.is_self:
            post_text = submission.selftext
            print(f"Text post found: {submission.title}")
        elif is_image_url(submission.url):
            print(f"Image post found: {submission.url}")
            post_text = extract_text_from_image(submission.url)
            if not post_text:
                post_text = "[Image] Unable to extract text from image."
        else:
            post_text = submission.url
            print(f"Non-text, non-image post found: {submission.url}")

        article_detail = {
            'Date': today_date,
            'Created On': post_creation_time.strftime('%Y-%m-%d %H:%M:%S'),
            'Subreddit': subreddit_name,
            'Title': submission.title,
            'URL': submission.url,
            'Score': submission.score,
            'Text': post_text,
            'Comments': [],  # This will hold the top-level comments
        }

        # Iterate over top-level comments only
        submission.comments.replace_more(limit=0)  # Prevent MoreComments from loading
        comment_min_score = 3 * hours_since_posted
        for top_level_comment in submission.comments:
            if isinstance(top_level_comment, Comment) and top_level_comment.score > comment_min_score:
                comment_dic = {
                    'Comment': top_level_comment.body,
                    'Comment_Score': top_level_comment.score
                }
                article_detail['Comments'].append(comment_dic)
            else:
                # Skip comments not meeting the score threshold
                print(f"Skipping comment with score {top_level_comment.score} (Minimum Required: {comment_min_score})")
                continue

        try:
            collection.insert_one(article_detail)
            print(f"Inserted article from {subreddit_name}: {submission.title}")
        except Exception as e:
            print(f"Error inserting into MongoDB: {e}")


# Prompts 1
prompts = {
    'Bitcoin': """You are a senior investment professional and I am a very sophisticated investor. The file is scraped data from reddit r/Bitcoin today, and it is limited to the most upvoted posts and comments. Please review the file in its entirety and give me a deep analysis of the following:
- based on the data, what is the general sentiment?
- score the sentiment between -100 to +100
- is there any good insights? (good as in providing useful data, pointing out correlation between things, identifying potential risks, depicting convincing scenarios, etc.)
- is there any noteworthy news about economics, technology, business, stock markets, or prominent figures comments (such as Elon Musk, Michael Saylor, Tim Draper, Jack Dorsey, Cathie Wood, and Trump)?""",
    'dogecoin': """You are a senior investment professional and I am a very sophisticated investor. The file is scraped data from reddit r/dogecoin today, and it is limited to the most upvoted posts and comments. Please review the file in its entirety and give me a deep analysis of the following:
- based on the data, what is the general sentiment?
- score the sentiment between -100 to +100
- is there any good insights? (good as in providing useful data, pointing out correlation between things, identifying potential risks, depicting convincing scenarios, etc.)
- is there any noteworthy news about economics, technology, business, stock markets, or prominent figures comments (such as Elon Musk, Michael Saylor, Tim Draper, Jack Dorsey, Cathie Wood, and Trump)?""",
}

#Prompt 2
newsletter = "Generate a PDF newsletter using the following analysis, focusing on key takeaways. Only return the PDF URL."

def gpt_data():
    for subreddit in subreddits:
    data = list(nt.find({"$and":[{"Subreddit":subreddit},{"Date":{"$gt":str(datetime.datetime.strptime(today_date,"%Y-%m-%d")-datetime.timedelta(days=7))}}