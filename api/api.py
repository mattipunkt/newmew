import tidalapi.user
import tidalapi
from platformdirs import *
import os
import json
from datetime import datetime

appname = "newmew"
user_data_file = user_data_dir(appname) + "/credentials.json"



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
        credentials["expiry_time"] = expiry_time.strftime(format='%s')
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


config = tidalapi.Config()
session = tidalapi.Session(config)

login(session)
artists = get_artists(session)
check_releases(session, artists)
