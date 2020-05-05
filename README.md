# GitHub Notify RSS

This is a simple localhost RSS feed proxy for your github notifications.

## Configuration

Simply [set up a GitHub API token](https://help.github.com/en/github/authenticating-to-github/creating-a-personal-access-token-for-the-command-line) with the `notifications` entitlement enabled.

## Use case

I use this to consume my GitHub notifications with emacs elfeed because it has great narrowing capabilities which allows me to sort, slice, and dice my notifications more effectively.

Obviously you can also use this with whatever other RSS reader but I'm not sure that gets you much over the standard github notifications interface.

I don't recommend you expose the RSS server to the world. If you do, put it behind TLS and auth.
