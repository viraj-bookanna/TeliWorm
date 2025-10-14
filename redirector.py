import os
from aiohttp import web
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from dotenv import load_dotenv
import logging

logging.basicConfig(level=logging.INFO)

def get_config(key, default=None):
    result = mongo_client.default.config.find_one({'key': key})
    return default if result is None else result['value']

async def show(request):
    return web.Response(text=f"https://t.me/{get_config('BOT_USERNAME')}")

async def redirect_handler(request):
    if 'bot' in request.headers.get('User-Agent', 'Unknown').lower():
        return web.Response(text=html, headers={'Content-Type': 'text/html'})
    headers = {
        "Location": f"https://t.me/{get_config('BOT_USERNAME')}",
        "Referrer-Policy": "no-referrer"
    }
    return web.Response(text="Moved Permanently", headers=headers, status=301)

async def redir_tg(request):
    headers = {
        "Location": "https://t.me/+42777",
        "Referrer-Policy": "no-referrer"
    }
    return web.Response(text="Moved Permanently", headers=headers, status=301)

load_dotenv(override=True)
mongo_client = MongoClient(os.environ['MONGODB_URI'], server_api=ServerApi('1'))
app = web.Application()
app.router.add_get('/url', show)
app.router.add_get('/tg', redir_tg)
app.router.add_get('/{anything:.*}', redirect_handler)
html = '''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta property="og:description" content="Super hot vedios and photo, XxX 🔞 super sxey ndue 🔥. HOT MOEDLS" />
  <meta property="og:site_name" content="Natugy Kdis" />
  <meta property="og:title" content="Hot Buns - Natugy Kdis" />
  <meta property="og:image" content="https://www.zupimages.net/up/25/41/l1wm.jpg" />
  <meta property="og:type" content="website" />
  <meta property="og:image:width" content="315" />
  <meta property="og:image:height" content="600" />
</head>
<body>
  <h1>Welcome to Natugy Kdis</h1>
</body>
</html>'''

if __name__ == "__main__":
    web.run_app(app, port=int(os.getenv('REDIRECTOR_PORT', '5000')))
