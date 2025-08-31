from flask import Flask, redirect
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

load_dotenv(override=True)
app = Flask(__name__)
mongo_client = MongoClient(os.getenv('MONGODB_URI'), server_api=ServerApi('1'))

def getconfig(key, default=None):
    result = mongo_client.default.config.find_one({'key':key})
    if result is None:
        return default
    return result['value']

@app.route('/')
def redirect():
    return redirect(f"https://t.me/{getconfig('BOT_USERNAME')}", code=301)

if __name__ == "__main__":
    app.run()
