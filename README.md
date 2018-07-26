# IMAP email desktop notification

Python script for displaying desktop notification for new emails. 
Useful for Text based Mail User Agent which doesn't have desktop notification such as Mutt.

## Usage
notif --help

This program depends on libnotify and python-gobject, for Debian install with `apt-get install libnotify-bin python-gobject`

Copy config file notif.cfg to $HOME/.notif.cfg and run the script. 
You can also specify config file with -c. See config.cfg for example configuration.

If started with root, the program will drop to non root user, default is uid 1000. If your uid is not 1000, supply with argument -u or change the DEFAULT_UID within the script
