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

from threading import Thread

appname = "newmew"
user_data_file = user_data_dir(appname) + "/credentials.json"
load_dotenv()


bot = telebot.TeleBot(os.getenv("TELEGRAM_BOT_KEY"), parse_mode="MARKDOWN")



def bot_polling():
    bot.infinity_polling()


class Database:
    con = sqlite3.Connection
    cur = sqlite3.Cursor

    def __init__(self) -> None:
        if not os.path.exists(user_data_dir(appname)):
            print("created folder")
            path = user_data_dir(appname) + "/"
            os.makedirs(path, exist_ok=True)
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

    def get_users(self):
        return self.cur.execute("SELECT * FROM users")
    

    def create_user_table(self, user_id):
        self.cur.execute("CREATE TABLE IF NOT EXISTS user_"+ str(user_id) +" (id INTEGER PRIMARY KEY AUTOINCREMENT, artist STRING, title STRING, release_date STRING)")
        self.con.commit()


    def add_release_to_user_table(self, user_id, artist, album, release_date):
        self.cur.execute("INSERT OR IGNORE INTO user_"+ str(user_id) +" (artist, title, release_date) VALUES (?, ?, ?)", (artist, album, release_date))
        self.con.commit()

    def get_user_release(self, user_id, artist, album):
        return self.cur.execute("SELECT * FROM user_"+ str(user_id) +" WHERE artist=? AND title=?", (artist, album))
    

    def get_user_releases(self, user_id):
        return self.cur.execute("SELECT * FROM user_"+ str(user_id))


    def delete_user_release(self, user_id, release_id):
        self.cur.execute("DELETE FROM user_" + str(user_id) + " WHERE id=?", (release_id))
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



def check_releases(session, telegram_id):
    db = Database()
    artists = session.user.favorites.artists()
    for artist in artists:
        ep_singles = artist.get_ep_singles()
        for release in ep_singles:
            if ((datetime.now() - release.release_date).days) <= 2:
                already_sent_check = db.get_user_release(telegram_id, artist.name, release.name)
                if already_sent_check.fetchall() == []:
                    bot.send_message(telegram_id, "Found new EP/Single by *" + artist.name + "*: " + release.name)
                    db.add_release_to_user_table(telegram_id, artist.name, release.name, datetime.strftime(release.release_date, "%d-%m-%Y"))
                    print("Found new EP/Single: " + release.name)
        albums = artist.get_albums()
        for release in albums:
            if ((datetime.now() - release.release_date).days) <= 2:
                if ((datetime.now() - release.release_date).days) < 0:
                    already_sent_check = db.get_user_release(telegram_id, artist.name, release.name)
                    if already_sent_check.fetchall() == []:
                        bot.send_message(telegram_id, "Found new *UNRELEASED* Album by *" + artist.name + "*: " + release.name + "\n_Planned release date is "+ datetime.strftime(release.release_date, "%d.%m.%Y") + "_" )
                        db.add_release_to_user_table(telegram_id, artist.name, release.name, datetime.strftime(release.release_date, "%d-%m-%Y"))
                        print("Found new *UNRELEASED* Album: " + release.name)
                else:
                    already_sent_check = db.get_user_release(telegram_id, artist.name, release.name)
                    if already_sent_check.fetchall() == []:
                        bot.send_message(telegram_id, "Found new Album by *" + artist.name + "*: " + release.name)
                        db.add_release_to_user_table(telegram_id, artist.name, release.name, datetime.strftime(release.release_date, "%d-%m-%Y"))
                        print("Found new Album: " + release.name)
    db.close()



def periodic_user_check():
    print("Start user check!")
    db = Database()
    users = db.get_users()
    for user in users:
        db.create_user_table(user[1])
        session = tidalapi.Session()
        session.load_oauth_session(user[2], user[3], user[4], datetime.fromtimestamp(int(user[5])))
        print("Logged in as user: " + session.user.username)
        check_releases(session, user[1])
    db.close()



def periodic_clean_up():
    db = Database()
    users = db.get_users()
    for user in users:
        db.create_user_table(user[1])
        releases = db.get_user_releases(user[1]).fetchall()
        for release in releases:
            release_date = datetime.strptime(release[3], "%d-%m-%Y")
            if (datetime.now() - release_date).days > 2:
                db.delete_user_release(release[0])



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


def periodic():
    periodic_clean_up()
    periodic_user_check()
    time.sleep(259200)





if __name__ == '__main__':
    Thread(target=bot_polling).start()
    time.sleep(10)
    print("Start second thread")
    Thread(target=periodic).start()
