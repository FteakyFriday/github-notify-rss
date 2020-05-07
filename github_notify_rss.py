#!/usr/bin/env python3

# a simple bottle based proxy that will serve your github notifications as a localhost rss feed

# note: if you're using this with detail enabled, it can take quite some time to process e.g. all/detail
# even though this server streams it output to the client, some readers (e.g. elfeed) can become unhappy,
# to work around that, you can use the --keep-since mechanism, and initialize the first session with
# e.g. curl http://localhost:9999/notifications/all/detail outside of the unhappy reader, then connect
# your reader and it will serve from cache with no delay ... the next time you start with --keep-since
# it will restore the since state and only serve updates that came in after the last use of the proxy

import github # pip3 install pygithub
import bottle # pip3 install bottle

import os
import datetime
import time
import email.utils
import pickle

from xml.sax.saxutils import escape as xml_escape

class GitHubAPI:
    "Light wrapper around pygithub."

    def __init__(self):
        # create a notifications token for this
        self.token = os.environ['GITHUB_TOKEN']
        self.github = github.Github(login_or_token=self.token)

    def fetch_notifications(self, all=False, participating=False, since=None):
        if since == None:
            n = self.github.get_user().get_notifications(all=all, participating=participating)
        else:
            n = self.github.get_user().get_notifications(all=all, participating=participating, since=since)
        return n

class GitHubRSS(bottle.Bottle):
    "Github notifications RSS server."

    def __init__(self, keep_since=False):
        super(GitHubRSS, self).__init__()
        self.keep_since = keep_since
        self.github = GitHubAPI()
        self.route('/notifications', callback=lambda: self.serve_channel('all')) # default channel
        # default feed only needs "notifications" scope on your access token but is stuck with just api urls
        self.route('/notifications/<channel>', callback=lambda channel: self.serve_channel(channel))
        # detail feeds has better urls for clicking convenience but also requires "repo" scope on your access token to work
        self.route('/notifications/<channel>/detail', callback=lambda channel: self.serve_channel(channel, detail=True))
        # pulling all/detail can take a very long time to init, would recommend unread/detail instead
        self.channels = {'all' : {'since' : self.inflate_since('all'),
                                  'entries' : [],
                                  'filter' : None,
                                  'fetcher' : lambda since: self.github.fetch_notifications(all=True, since=since)},
                         'unread' : {'since' : self.inflate_since('unread'),
                                     'entries' : [],
                                     # for some reason all=False still gets us unread notifications, so add a filter
                                     'filter' : lambda n: n.unread == False,
                                     'fetcher' : lambda since: self.github.fetch_notifications(all=False, since=since)},
                         'participating' : {'since' : self.inflate_since('participating'),
                                            'entries' : [],
                                            'filter' : None,
                                            'fetcher' : lambda since: self.github.fetch_notifications(all=False, participating=True, since=since)}}

    # if you're playing around with the since state, remember to rm .gh_rss*state to reset state completely
    def inflate_since(self, channel):
        if self.keep_since == False:
            return None
        p = f'.gh_rss_{channel}_since_state'
        if os.path.exists(p) == False:
            print(f"rss: no since state to restore from for channel: {channel}")
            return None
        since_state = pickle.load(open(p, 'rb'))
        print(f"rss: restored since state for channel {channel}: %s" % self.dt_to_rfc2822(since_state))
        return since_state

    def deflate_since(self, channel):
        if self.keep_since == False:
            return
        since_state = self.channels[channel]['since']
        p = f'.gh_rss_{channel}_since_state'
        pickle.dump(since_state, open(p, 'wb'))
        print(f"rss: saved since state for channel {channel}: %s" % self.dt_to_rfc2822(since_state))

    def reset_channel(self, channel):
        self.channels[channel]['entries'] = []
        self.channels[channel]['since'] = None

    def xml_scrub(self, s):
        return xml_escape(s)

    def dt_to_rfc2822(self, dt):
        return email.utils.formatdate(time.mktime(dt.timetuple()))

    def update_channel(self, channel, detail=False):
        # get our new set of notifications
        notifications = self.channels[channel]['fetcher'](self.channels[channel]['since'])
        channel_updates = []
        update_since = True
        for n in notifications:
            if update_since == True:
                # we want to use the timestamp of the newest update as the floor for our boundary
                self.channels[channel]['since'] = n.updated_at + datetime.timedelta(seconds=1)
                self.deflate_since(channel)
                update_since = False
            # apply a channel filter if set, skip this notification if filter returns true
            filter = self.channels[channel]['filter']
            if filter != None and filter(n) == True:
                continue
            url = n.url
            link = "https://github.com/notifications"
            # subject url not always available, but it's what we want if it is, and if it is, we want the item link to be the non-api version
            if n.subject.url != None:
                url = n.subject.url
            # you need to enable repo scope on your token for this to work, warning, this can be very slow on the initial fetch
            if detail == True:
                try:
                    if n.subject.type.lower() == 'pullrequest':
                        print("Fetching PR url ...")
                        html_url = n.get_pull_request().html_url
                    elif n.subject.type.lower() == 'issue':
                        print("Fetching issue url ...")
                        html_url = n.get_issue().html_url
                    link = html_url
                except github.GithubException as e:
                    print("rss: failed to fetch detail url, enable repo scope on token if you want this to work ...")
                    pass
            # see if we can get an html url for the related issue or pull request
            n_dict = {
                'title' : n.subject.title,
                'url' : url,
                'type' : n.subject.type,
                'repo' : n.repository.full_name,
                'reason' : n.reason,
                'updated_at' : self.dt_to_rfc2822(n.updated_at),
                'unread' : n.unread,
                'link' : link
            }
            channel_updates.append(n_dict)
            # yield our update
            yield n_dict
        # now yield the stuff we already had
        for n_dict in self.channels[channel]['entries']:
            yield n_dict
        # toss newer entries at the head of the list
        self.channels[channel]['entries'] = channel_updates + self.channels[channel]['entries']

    def item_to_entry(self, rss_item):
        description  = self.xml_scrub(f'unread: {rss_item["unread"]}<br>')
        description += self.xml_scrub(f'reason: {rss_item["reason"]}<br>')
        description += self.xml_scrub(f'type: {rss_item["type"]}<br>')
        description += self.xml_scrub(f'repo: {rss_item["repo"]}<br>')
        description += self.xml_scrub(f'url: {rss_item["url"]}<br>')
        description += self.xml_scrub(f'updated at: {rss_item["updated_at"]}')
        title = self.xml_scrub(f'{rss_item["reason"]}: {rss_item["title"]} ({rss_item["repo"]})')
        link = self.xml_scrub(rss_item["link"])
        pubdate = self.xml_scrub(rss_item["updated_at"])
        guid = self.xml_scrub(rss_item["url"]) + pubdate + title
        return f'<item><title>{title}</title><link>{link}</link><guid>{guid}</guid><pubDate>{pubdate}</pubDate><description>{description}</description></item>'

    def serve_channel(self, channel, detail=False):
        if channel not in self.channels:
            return bottle.HTTPError(404, "Channel not found")
        def yield_rss_body(channel, detail):
            rss_head  = '<?xml version="1.0" encoding="utf-8"?>'
            rss_head += '<rss version="2.0">'
            rss_head += '<channel>'
            rss_head += '<title>GitHub Notifications</title>'
            rss_head += '<link>https://github.com/notifications</link>'
            rss_head += '<description>GitHub Notifications</description>'
            rss_head += '<language>en-us</language>'
            yield rss_head
            for rss_item in self.update_channel(channel, detail=detail):
                yield self.item_to_entry(rss_item)
            rss_tail  = '</channel>'
            rss_tail += '</rss>'
            yield rss_tail
        return yield_rss_body(channel, detail)

    def serve_feeds(self, host, port):
        self.run(host=host, port=port)

import argparse

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='GitHub Notify RSS proxy - v0.1')
    parser.add_argument('--host', type=str, help='host interface to listen on (defaults to localhost)', default='127.0.0.1')
    parser.add_argument('--port', type=int, help='port to listen on (defaults to 9999)', default=9999)
    parser.add_argument('--keep-since', help='save/restore channel timestamp since last session (prevents re-fetching)', action='store_true')
    args = parser.parse_args()
    GitHubRSS(keep_since=args.keep_since).serve_feeds(args.host, args.port)
