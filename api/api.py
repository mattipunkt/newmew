import tidalapi.user
import tidalapi
from platformdirs import *
import os
import json
from datetime import datetime
import sqlite3
import telebot
from dotenv import load_dotenv
import io
import contextlib
import time

appname = "newmew"
user_data_file = user_data_dir(appname) + "/credentials.json"
load_dotenv()


class Database:
    con = sqlite3.Connection
    cur = sqlite3.Cursor

    def __init__(self) -> None:
        self.con = sqlite3.connect(user_data_dir(appname) + "/database.sqlite")
        self.cur = self.con.cursor()
        self.cur.execute(
            "CREATE TABLE IF NOT EXISTS users (\
            id INTEGER PRIMARY KEY AUTOINCREMENT,\
            telegram_user_id INTEGER,\
            tidal_token_type STRING,\
            tidal_access_token STRING,\
            tidal_refresh_token STRING,\
            tidal_expiry_time STRING)"
            )
        pass

    def add_user(self, telegram_user_id, tidal_token_type, tidal_access_token, tidal_refresh_token, tidal_expiry_time):
        self.cur.execute("INSERT OR IGNORE INTO USERS(telegram_user_id, tidal_token_type, tidal_access_token, tidal_refresh_token, tidal_expiry_time) VALUES (?, ?, ?, ?, ?)", (telegram_user_id, tidal_token_type, tidal_access_token, tidal_refresh_token, tidal_expiry_time))
        self.con.commit()

    def check_existing_user(self, telegram_user_id):
        user = self.cur.execute("SELECT id FROM users where telegram_user_id='"+ str(telegram_user_id) +"'")
        if user.fetchall() == []:
            return False
        else:
            return True
    
    def delete_user(self, telegram_user_id):
        self.cur.execute("DELETE FROM users WHERE telegram_user_id='" + str(telegram_user_id) + "'")
        self.con.commit()


    def close(self):
        self.con.close()




def login(session):
    if os.path.isfile(user_data_file):
        with open(user_data_file, "r") as fp:
            credentials = json.load(fp)
        session.load_oauth_session(credentials["token_type"], credentials["access_token"], credentials["refresh_token"], datetime.fromtimestamp(int(credentials["expiry_time"])))

    else:
        session.login_oauth_simple()
        credentials = dict()
        credentials["token_type"] = session.token_type
        credentials["access_token"] = session.access_token
        credentials["refresh_token"] = session.refresh_token
        expiry_time = session.expiry_time
        credentials["expiry_time"] = session.expiry_time.strftime(format='%s')
        if not os.path.exists(user_data_dir(appname)):
            print("created folder")
            path = user_data_dir(appname) + "/"
            os.mkdir(path)
        with open(user_data_file, 'w+') as fp:
            print("Saving credentials")
            json.dump(credentials, fp)


    if session.check_login() is True:
        print("Successfully logged in to TIDAL API!")


def get_artists(session):
    return session.user.favorites.artists()
    
        

def check_releases(session, artists):
    for artist in artists:
        print(artist.name)
        ep_singles = artist.get_ep_singles()
        for release in ep_singles:
            if ((datetime.now() - release.release_date).days) <= 2:
                print("Found new EP/Single: " + release.name)
        albums = artist.get_albums()
        for release in albums:
            if ((datetime.now() - release.release_date).days) <= 2:
                if ((datetime.now() - release.release_date).days) < 0:
                    print("Found new UNRELEASED Album : " + release.name)
                else:
                    print("Found new Album: " + release.name)



#Periodic Task




bot = telebot.TeleBot(os.getenv("TELEGRAM_BOT_KEY"), parse_mode="MARKDOWN") # You can set parse_mode by default. HTML or MARKDOWN


@bot.message_handler(commands=['start'])
def send_welcome(message):
    db = Database()
    if db.check_existing_user(message.chat.id) is True:
        bot.send_message(message.chat.id, "Whoa, slowly! You are already registered in the release search bot.")
    else:
        bot.send_message(message.chat.id, "Hey there!\n\nThis Bot checks your favorite TIDAL-Artists twice a day for new releases and sends you a message, when there is one!")
        bot.send_message(message.chat.id, "Be aware that, if you login in the next step, your login keys (not your passwords) are stored in the database. Without that, the bot could not search through your saved artists!\nThis would allow me to use your account through the TIDAL-API. *However, there no passwords saved!*\n\nBy sending the command /stop, all of your data on this bot will be safely deleted.")
        config = tidalapi.Config()
        session = tidalapi.Session(config)
        with contextlib.redirect_stdout(io.StringIO()) as f:
            link = session.login_oauth()
            print(link[0].verification_uri_complete)
            bot.send_message(message.chat.id, "Click this link and login to TIDAL: \n\n" + f.getvalue() + "\nThis link is valid for 300 seconds.")
            while link[1].running() is True:
                time.sleep(1)
            if link[1].done() is True:
                bot.send_message(message.chat.id, "Your login was successful!")
                db.add_user(message.chat.id, session.token_type, session.access_token, session.refresh_token, str(session.expiry_time.strftime(format='%s')))
            else:            
                bot.send_message(message.chat.id, "There was an error while logging you in!")
    db.close()


@bot.message_handler(commands=['stop'])
def send_stop(message):
    db = Database()
    if db.check_existing_user(message.chat.id) is True:
        bot.send_message(message.chat.id, "Ok, your credentials and data will be deleted!\nThank you for using this bot. :D")
        db.delete_user(message.chat.id)
    else:
        bot.send_message(message.chat.id, "Hhmmm??!?!?")
    db.close()




bot.infinity_polling()