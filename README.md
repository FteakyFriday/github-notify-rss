# GitHub Notify RSS

This is a simple localhost RSS feed proxy for your github notifications.

It exposes the following RSS channels:

- `all`, which includes all your github notifications
- `unread`, which includes only unread notifications
- `participating`, which includes notifications for anything you are participating or mentioned in

To use a specific channel you can point your reader to `http://your.proxy:port/notifications/<channel>`.

The `/notifications` endpoint defaults to the `all` channel, with no `detail` enabled.

Alternatively, you can request more `detail` for channel items via `/notifications/<channel>/detail`. This will add e.g. the html url versions of the issues and PRs for clicking convenience (due to how the GitHub v3 API works, you're stuck with api specific URLs by default).

## Usage

```
usage: github_notify_rss.py [-h] [--host HOST] [--port PORT] [--keep-since]

GitHub Notify RSS proxy - v0.1

optional arguments:
  -h, --help    show this help message and exit
  --host HOST   host interface to listen on (defaults to localhost)
  --port PORT   port to listen on (defaults to 9999)
  --keep-since  save/restore channel timestamp since last session (prevents
                re-fetching)
```

## Configuration

[Set up a GitHub API token](https://help.github.com/en/github/authenticating-to-github/creating-a-personal-access-token-for-the-command-line) with the `notifications` entitlement enabled and pass this to the proxy through the `GITHUB_TOKEN` environment variable.

e.g.:
```
$ GITHUB_TOKEN=`cat ~/.github-notifier-token` python3 github_notify_rss.py --keep-since
rss: restored since state for channel all: Wed, 06 May 2020 23:34:22 -0000
rss: no since state to restore from for channel: unread
Bottle v0.12.18 server starting up (using WSGIRefServer())...
Listening on http://127.0.0.1:9999/
Hit Ctrl-C to quit.
```

NOTE: If you want to use the `detail` enabled feeds on _private_ repos, you also need the `repo` entitlement enabled on the token.

## Use case

I use this to consume my GitHub notifications with [elfeed](https://github.com/skeeto/elfeed) because it has great narrowing capabilities which allows me to sort, slice, and dice my notifications more effectively, without having to leave emacs too much. For emacs context I only care about the `participating` channel, so I configure my elfeed as such:

```elisp
  (when (eql my/location 'work)
    (setq elfeed-feeds
          (append '(("https://github.com/security-advisories" github infosec advisories)
                    ("http://localhost:9999/notifications/participating/detail" github notifications participating))
                  elfeed-feeds)))
```

Obviously you can also use this with whatever other RSS reader but I'm not sure that gets you much over the standard github notifications interface :)

I don't recommend you expose the RSS server to the world. If you do, put it behind TLS and auth.

## Known Issues

When using a `detail` enabled channel, the RSS proxy has to make additional GitHub API requests to fetch the additional detail for each item. This significantly increases the processing time when you are initializing very large sets of notifications and some readers may time out on the channel fetch, even though the proxy properly streams the items to the client.

This is generally only an issue the first time you use the proxy, any additional fetches in an existing session will have an updated `since` state that only fetch any new notifications. To retain this `since` state, you can use the `--keep-since` option. This will prevent unecessary re-fetching on future sessions of the proxy.

Any existing notifications are served out of cache as long as the proxy is active.

To init the proxy cache, you can use something like `curl` to make a request to the channel you want to intialize before pointing you reader to it. e.g. `curl http://localhost:9999/notifications/all/detail` will initialilize the `all` channel with `detail` enabled.

Again, this is only required if your reader does not like slow feeds. Subsequent requests will be served out of cache, and only new notifications since the last fetch will require processing.

To fully reset the `since` state, quit the proxy and `rm .gh_rss*state`. This is really only required when you want your reader to re-fetch and re-process the existing notifications for a channel.
