#!/usr/bin/env python3

# a simple bottle based proxy that will serve your github notifications as a localhost rss feed

# for creating a notifications token see:
# https://help.github.com/en/github/authenticating-to-github/creating-a-personal-access-token-for-the-command-line

import github # pip3 install pygithub
import bottle # pip3 install bottle

import os
import datetime
import time
import email.utils

from xml.sax.saxutils import escape as xml_escape

class GitHubAPI:
    "Light wrapper around pygithub."

    def __init__(self):
        # create a notifications token for this
        self.token = os.environ['GITHUB_TOKEN']
        self.github = github.Github(login_or_token=self.token)

    def fetch_notifications(self, since=None):
        if since == None:
            n = self.github.get_user().get_notifications(all=True)
        else:
            n = self.github.get_user().get_notifications(all=True, since=since)
        return n

class GitHubRSS(bottle.Bottle):
    "Github notifications RSS server."

    def __init__(self):
        super(GitHubRSS, self).__init__()
        self.github = GitHubAPI()
        self.route('/notifications', callback=lambda: self.serve_channel('all'))
        self.channels = { 'all' : {'since' : None, 'entries' : []} }

    def reset_channel(self, channel):
        self.channels[channel]['entries'] = []
        self.channels[channel]['since'] = None

    def xml_scrub(self, s):
        return xml_escape(s)

    def update_channel(self, channel):
        notifications = self.github.fetch_notifications(since=self.channels[channel]['since'])
        self.channels[channel]['since'] = datetime.datetime.today()
        channel_updates = []
        for n in notifications:
            n_dict = {
                'title' : n.subject.title,
                'url' : n.url,
                'type' : n.subject.type,
                'repo' : n.repository.full_name,
                'reason' : n.reason,
                'updated_at' : email.utils.formatdate(time.mktime(n.updated_at.timetuple())),
                'unread' : n.unread
            }
            channel_updates.append(n_dict)
        # toss newer entries at the head of the list
        self.channels[channel]['entries'] = channel_updates + self.channels[channel]['entries']

    def item_to_entry(self, rss_item):
        description = self.xml_scrub(f'unread: {rss_item["unread"]}\nreason: {rss_item["reason"]}\ntype: {rss_item["type"]}\nrepo: {rss_item["repo"]}\nurl: {rss_item["url"]}'.replace('\n', '<br>'))
        title = self.xml_scrub(f'{rss_item["reason"]}: {rss_item["title"]} ({rss_item["repo"]})')
        link = self.xml_scrub("https://github.com/notifications")
        pubdate = self.xml_scrub(rss_item["updated_at"])
        guid = self.xml_scrub(rss_item["url"]) + pubdate + title
        return f'<item><title>{title}</title><link>{link}</link><guid>{guid}</guid><pubDate>{pubdate}</pubDate><description>{description}</description></item>'

    def serve_channel(self, channel):
        self.update_channel(channel)
        rss_body  = '<?xml version="1.0" encoding="utf-8"?>'
        rss_body += '<rss version="2.0">'
        rss_body += '<channel>'
        rss_body += '<title>GitHub Notifications</title>'
        rss_body += '<link>https://github.com/notifications</link>'
        rss_body += '<description>GitHub Notifications</description>'
        rss_body += f'<lastBuildDate>{self.channels[channel]["since"]}</lastBuildDate>'
        rss_body += '<language>en-us</language>'
        for rss_item in self.channels[channel]['entries']:
            rss_body += self.item_to_entry(rss_item)
        rss_body += '</channel>'
        rss_body += '</rss>'
        return rss_body

    def serve_feeds(self):
        self.run(host='127.0.0.1', port=9999)

if __name__ == '__main__':
    r = GitHubRSS()
    r.serve_feeds()
