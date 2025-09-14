import os
from aiohttp import web
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from dotenv import load_dotenv

def get_config(key, default=None):
    result = mongo_client.default.config.find_one({'key': key})
    return default if result is None else result['value']

async def show(request):
    return web.Response(text=f"https://t.me/{get_config('BOT_USERNAME')}")

async def redirect_handler(request):
    headers = {
        "Location": f"https://t.me/{get_config('BOT_USERNAME')}",
        "Referrer-Policy": "no-referrer"
    }
    return web.Response(text="Moved Permanently", headers=headers, status=301)

load_dotenv(override=True)
mongo_client = MongoClient(os.environ['MONGODB_URI'], server_api=ServerApi('1'))
app = web.Application()
app.router.add_get('/url', show)
app.router.add_get('/{anything:.*}', redirect_handler)

if __name__ == "__main__":
    web.run_app(app, port=int(os.getenv('REDIRECTOR_PORT', '5000')))
