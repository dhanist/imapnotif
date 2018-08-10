#!/usr/bin/env python3

import gi
gi.require_version('Notify', '0.7')
from gi.repository import Notify, GLib
import configparser
import argparse
import os, sys, logging, logging.handlers
from html import escape as html_escape
import resource, signal
from pwd import getpwnam
from threading import Thread
import mailbox
import email
import time

'''
Please secure the config file with chmod 600 as this program runs
non interactive so we need to read plaintext password
'''
CONFIG_FILE     = "%s/.notif.cfg" % (os.environ["HOME"])
DEVLOG          = "/dev/log"
DEVNULL         = "/dev/null"
DEFAULT_MAILBOX = "INBOX"
INTERVAL        = 10
IDLE_TIMEOUT    = 15        # when using imap idle, value in minute
DEFAULT_UID     = 1000
VERBOSE         = False
MAILBOXES       = []        # holding account isntances
SYS_EXIT        = False

class Notif:
    def __init__(self, **kwargs):
        self._data = kwargs.get("data")
        self._summ = kwargs.get('summary')
        self._body = kwargs.get('body')
        self._icon = kwargs.get('icon')
        self._func = kwargs.get('callback')

        self._notif = Notify.Notification.new(self._summ, self._body)
        self._notif.add_action("click", "Mark read", self._callback, self._data)

    def _callback(self, notif, act, data):
        try:
            self._func(data)
        except: pass

    def show(self):
        self._notif.show()

def close_imap(signum, blah=None):
    if VERBOSE:
        log.info("Receiving signal number %d, exiting..." % (signum))

    global SYS_EXIT
    SYS_EXIT = True

    if GLib.MainLoop().is_running():
        GLib.MainLoop().quit()

    for m in MAILBOXES:
        if VERBOSE:
            log.info("{} - {}: closing thread.".format(
                m._account.name,
                m.name))
        if m.status & mailbox.Mailbox.CLOSED > 0:
            continue
        try:
            Thread(target=m.close).start()
        except: pass

    time.sleep(5)
    sys.exit(0)

def build_config():
    l = []

    if args.config:
            cfg_file = args.config
    else:   cfg_file = CONFIG_FILE
    cfg = configparser.ConfigParser()
    try:
        cfg.read(cfg_file)
    except:
        os.stderr.write("Unable to read config file, exiting..\n")
        sys.exit(1)

    for i in cfg.sections():
        d = {}
        d["name"] = i

        opts = cfg.options(i)
        for opt in opts:
            try:
                d[opt] = cfg.get(i, opt)
            except:
                d[opt] = None

        if not "mailboxes" in d or d["mailboxes"] == "":
            d["mailboxes"] = DEFAULT_MAILBOX

        if "interval" in d:
            try:
                    d["interval"] = int(d["interval"])
            except: d["interval"] = INTERVAL
        else:
            d["interval"] = INTERVAL

        if not "server" in d or d["server"] == "":
            sys.stderr.write("%s will not be checked: " % d["name"])
            sys.stderr.write("server not defined in config file\n")
            continue
        if not "username" in d or d["username"] == "":
            sys.stderr.write("%s will not be checked: " % d["name"])
            sys.stderr.write("user not defined in config file\n")
            continue
        if not "password" in d or d["password"] == "":
            sys.stderr.write("%s will not be checked: " % d["name"])
            sys.stderr.write("password not defined in config file\n")
            continue

        l.append(d)

    return l

def daemonize():
    try:
        pid = os.fork()
    except Exception as e:
        os.stderr.write("%s\n" % (e))
        sys.exit(1)

    if pid == 0:
        os.setsid()

        try:
            pid = os.fork()
        except Exception as e:
            os.stderr.write("%s\n" % (e))
            sys.exit(1)

        if pid == 0:
            os.chdir("/")
            os.umask(0)
        else:
            os._exit(0)

    else:
        os._exit(0)

    if os.getuid() == 0:
        os.setuid(uid)

    fd = resource.getrlimit(resource.RLIMIT_NOFILE)[1]
    if fd == resource.RLIM_INFINITY:
        fd = MAXFD

    sys.stdout.flush()
    sys.stderr.flush()

    devnull = os.open(DEVNULL, os.O_RDWR)

    os.dup2(devnull, sys.stdin.fileno())
    os.dup2(devnull, sys.stdout.fileno())
    os.dup2(devnull, sys.stderr.fileno())

def show_notif(num, mbox):
    if not isinstance(num, str):
        return

    msg = mbox.fetch(num, mailbox.Mailbox.FETCH_HEADER)
    if not isinstance(msg, email.message.Message):
        return

    email_from = msg["from"].split('<')[0].replace("\"", "")
    notif_body = html_escape("{}\n\n{}".format(
        email_from,
        msg["subject"].replace("\"", "")))
    notif_summ = html_escape("{}: {}".format(
        mbox._account.name,
        mbox.name.replace("\"", "")))
    notif = Notif(
        body     = notif_body,
        summary  = notif_summ,
        data     = num,
        callback = mbox.mark_read
    ).show()

def idle(mbox):
    while mbox.status & mbox.IDLE_FAILED == 0:
        try:
            data = mbox.idle()
        except:
            break

        if data is None:
            if VERBOSE:
                log.info("{} - {}: idle ended, retrying..".format(
                    mbox._account.name,
                    mbox.name))
            continue

        if 'exists' in data:
            if VERBOSE:
                log.info("{} - {}: new message".format(
                    mbox._account.name,
                    mbox.name))

            num = data.split()[1]
            show_notif(num, mbox)

    if VERBOSE:
        log.info("{} - {}: idle failed".format(
            mbox._account.name,
            mbox.name))

def poll(mbox, interval):
    nums = mbox.poll()
    if nums is not None:
        for num in nums:
            show_notif(num.decode('utf-8'), mbox)

def loop(mbox, interval=INTERVAL):
    while 1:
        if SYS_EXIT:
            break

        if VERBOSE:
            log.info("{} - {}: initiating connection".format(
                mbox._account.name,
                mbox.name))

        if mbox.status & mailbox.Mailbox.CLOSED > 0:
            try:
                if not mbox.open():
                    time.sleep(60 - time.localtime().tm_sec)
                    continue
            except:
                if VERBOSE:
                    log.info("{} - {}: network error, waiting..".format(
                        mbox._account.name,
                        mbox.name))
                time.sleep(60 - time.localtime().tm_sec)
                continue


        tm_min = time.localtime().tm_min
        if tm_min % interval == 0:
            if VERBOSE:
                log.info("{} - {}: polling server..".format(
                    mbox._account.name,
                    mbox.name))
            poll(mbox, interval)

        if 'IDLE' in mbox._imap.capabilities:
            if VERBOSE:
                log.info("{} - {}: trying imap idle..".format(
                    mbox._account.name,
                    mbox.name))
            try: idle(mbox)
            except:
                continue
            time.sleep(1)
        else:
            time.sleep(60 - time.localtime().tm_sec)

    if VERBOSE:
        log.info("{} - {}: thread exited..".format(
            mbox._account.name,
            mbox.name))

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)
handler = logging.handlers.SysLogHandler(address = DEVLOG)
handler.setFormatter(logging.Formatter('%(module)s: %(message)s'))
log.addHandler(handler)

parser = argparse.ArgumentParser(description="IMAP Desktop Notification")
parser.add_argument("-c", "--config", help="configuration file")
parser.add_argument("-u", "--user", help="Run daemon as user")
args = parser.parse_args()

if args.user:
        try:    uid = getpwnam(args.user).pw_uid
        except: pass
else:   uid = DEFAULT_UID

signal.signal(signal.SIGTERM, close_imap)
signal.signal(signal.SIGINT, close_imap)

if __name__ == '__main__':
    accounts = build_config()
    if len(accounts) == 0:
        sys.stderr.write("No accounts defined, exiting..\n")
        sys.exit(1)

    daemonize()
    Notify.init("imapnotif")

    for account in accounts:
        a = mailbox.Account()
        a.server   = account["server"]
        a.username = account["username"]
        a.password = account["password"]
        a.name     = account["name"]

        if 'ssl' in account and int(account['ssl']) == 1:
            a.ssl  = True

        i = INTERVAL
        if 'interval' in account:
            i = account['interval']

        if not 'mailboxes' in account:
            account['mailboxes'] = DEFAULT_MAILBOX

        for m in account["mailboxes"].split(","):
            mbox = mailbox.Mailbox(a, name=m)
            MAILBOXES.append(mbox)

            try:
                if mbox.open():
                    poll(mbox, i)
            except: pass

    for M in MAILBOXES:
        Thread(target=loop, args=(M,)).start()

    GLib.unix_signal_add(GLib.PRIORITY_HIGH, signal.SIGINT, close_imap, signal.SIGINT)
    GLib.unix_signal_add(GLib.PRIORITY_HIGH, signal.SIGTERM, close_imap, signal.SIGTERM)
    try: GLib.MainLoop().run()
    except: pass
