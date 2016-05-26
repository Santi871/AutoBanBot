import praw
import OAuth2Util
import threading
import time
import traceback
import requests.exceptions
import configparser


class CreateThread(threading.Thread):
    def __init__(self, thread_id, name, method, r, user):
        threading.Thread.__init__(self)
        self.threadID = thread_id
        self.name = name
        self.method = method
        self.r = r
        self.user = user

    def run(self):

        # This loop will run when the thread raises an exception
        while True:
            try:
                if self.user is None:
                    methodToRun = self.method(self.r)
                else:
                    methodToRun = self.method(self.r, self.user)
            except:
                print("*Unhandled exception"
                      " in thread* '%s'. Attempting to restart thread..." % self.name)
                print(traceback.format_exc())
                time.sleep(1)


class AutoBanBot:

    def __init__(self, useragent, config_name):

        self.useragent = useragent

        # Parse config
        config = configparser.ConfigParser()
        config.read(config_name)

        self.subreddit = config.get('bot', 'subreddit')
        self.blacklisted_subs = config.get('bot', 'blacklisted_subs').split(',')
        self.comments_limit = config.get('bot', 'comment_history_limit')
        self.submissions_limit = config.get('bot', 'submission_history_limit')
        self.bans_duration = config.get('bans', 'ban_length')
        self.test_mode = config.getboolean('bot', 'test_mode')

    def run(self):

        self._create_thread(self._new_submissions_stream)
        self._create_thread(self._new_comments_stream)

    def _create_thread(self, method, user=None):

        # Threads need their own authenticated reddit instance, so we make one
        app_uri = 'https://127.0.0.1:65010/authorize_callback'
        thread_r = praw.Reddit(user_agent=self.useragent)
        o = OAuth2Util.OAuth2Util(thread_r)
        o.refresh(force=True)
        thread_r.config.api_request_delay = 1

        # Create a thread with the method and reddit instance we called
        thread = CreateThread(1, str(method) + " thread", method, thread_r, user)
        thread.start()

    def _new_submissions_stream(self, r):

        while True:

            try:
                for submission in praw.helpers.submission_stream(r, self.subreddit, limit=2, verbosity=0):
                    self._create_thread(self._handle_user, user=submission.author)
            except (TypeError, praw.errors.HTTPException, requests.exceptions.ReadTimeout):
                time.sleep(1)
                continue
            except:
                print(traceback.format_exc())

    def _new_comments_stream(self, r):

        while True:

            try:
                for submission in praw.helpers.comment_stream(r, self.subreddit, limit=2, verbosity=0):
                    self._create_thread(self._handle_user, user=submission.author)
            except (TypeError, praw.errors.HTTPException, requests.exceptions.ReadTimeout):
                time.sleep(1)
                continue
            except:
                print(traceback.format_exc())

    def _handle_user(self, r, username):

        user = r.get_redditor(username)
        sub_obj = r.get_subreddit(self.subreddit)
        exit = False

        ban_reason = "You have been automatically banned for participating in: "
        mod_reason = "Automatic ban performed by AutoBanBot. User participates in: "

        if self.submissions_limit:

            for submission in user.get_submissions(limit=self.submissions_limit):

                if submission.subreddit in self.blacklisted_subs:

                    ban_reason += "/r/" + submission.subreddit
                    mod_reason += "/r/" + submission.subreddit

                    if not self.test_mode:
                        sub_obj.add_ban(username, duration=self.bans_duration, ban_reason=mod_reason,
                                        ban_message=ban_reason)

                    print("Banned user: /u/" + username)

                    exit = True
                    break

        if self.comments_limit and not exit:

            for comment in user.comments(limit=self.comments_limit):

                if comment.subreddit in self.blacklisted_subs:
                    ban_reason += "/r/" + comment.subreddit
                    mod_reason += "/r/" + comment.subreddit

                    if not self.test_mode:
                        sub_obj.add_ban(username, duration=self.bans_duration, ban_reason=mod_reason,
                                        ban_message=ban_reason)

                    print("Banned user: /u/" + username)
                    break
