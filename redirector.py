from flask import Flask, Response
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

load_dotenv(override=True)
app = Flask(__name__)
mongo_client = MongoClient(os.environ['MONGODB_URI'], server_api=ServerApi('1'))

def getconfig(key, default=None):
    result = mongo_client.default.config.find_one({'key':key})
    if result is None:
        return default
    return result['value']

@app.route('/url')
def show():
    return f"https://t.me/{getconfig('BOT_USERNAME')}"

@app.route('/lol', defaults={'anything': ''})
@app.route('/<path:anything>')
def redirect():
    headers = {"Location": f"https://t.me/{getconfig('BOT_USERNAME')}", "Referrer-Policy": "no-referrer"}
    return Response("Moved Permanently", headers=headers, status=301)

if __name__ == "__main__":
    app.run()
