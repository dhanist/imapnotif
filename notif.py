#!/usr/bin/env python3

import gi
gi.require_version('Notify', '0.7')
gi.require_version('Gtk', '3.0')
from gi.repository import Notify, GLib, Gtk
import configparser
import argparse
import os, sys, logging, logging.handlers
from html import escape as html_escape
import resource, signal
from pwd import getpwnam
from threading import Thread
import notiflib, view
import email
from email.header import make_header, decode_header
import time
import subprocess

import traceback

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
VERBOSE         = True
MAILBOXES       = []        # holding account isntances
SYS_EXIT        = False

track           = {}
MAX_BYTE        = 128
class Track:
    def __init__(self):
        self._mnum = bytearray(MAX_BYTE)

    def set_bit(self, num):
        i = num % (MAX_BYTE * 8)
        self._mnum[i >> 3] |= (1 << (i % 0x07))

    def ck_bit(self, num):
        i = num % (MAX_BYTE * 8)
        if self._mnum[i >> 3] & (1 << (i % 0x07)) > 0:
            return True
        return False

    def clr_bit(self, num):
        i = num % (MAX_BYTE * 8)
        self._mnum[i >> 3] &= ~(1 << (i % 0x07))


class Notif:
    def __init__(self, **kwargs):
        self._summ = kwargs.get('summary')
        self._body = kwargs.get('body')
        self._icon = kwargs.get('icon')
        self._func = {}

        self._notif = Notify.Notification.new(self._summ, self._body)

    def _callback(self, notif, act, data):
        func = self._func.get(act)
        if func is None:
            return
        try:
            func(data)
        except: pass

    def show(self):
        self._notif.show()

    def add_callback(self, label, func, data = None):
        self._func[label] = func
        self._notif.add_action(label, label, self._callback, data)

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
        if m.status & notiflib.IMAP_Mailbox.CLOSED > 0:
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

        if d['password'].startswith('`') and d['password'].endswith('`'):
            passwd = getpass(d['password'])
            d['password'] = passwd

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

    msg = mbox.fetch(num, notiflib.IMAP_Mailbox.FETCH_HEADER)
    if not isinstance(msg, email.message.Message):
        return

    email_from = msg["from"].split('<')[0].replace("\"", "")
    notif_body = html_escape("{}\n\n{}".format(
        email_from,
        make_header(decode_header(msg.get('subject'))))
    )
    notif_summ = html_escape("{}: {}".format(
        mbox._account.name,
        mbox.name.replace("\"", ""))
    )
    notif = Notif(
        body     = notif_body,
        summary  = notif_summ,
    )
    notif.add_callback("View", view_msg,
            {"account":mbox._account, "num":num, "inbox": mbox.name})
    notif.add_callback("Mark read", mbox.mark_read, num)
    notif.show()

    track[mbox._account.name].set_bit(int(num))

def view_msg(data):
    try:
        account = data.get("account")
        num     = data.get("num")
        inbox   = data.get("inbox")
        if account is None or num is None:
            return
        win = view.ViewMsg(account, inbox, num)
        win.connect('destroy', Gtk.main_quit)
        win.show_all()

        Gtk.main()
    except:
        traceback.print_exc()

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
            poll(mbox)

    if VERBOSE:
        log.info("{} - {}: idle failed".format(
            mbox._account.name,
            mbox.name))

def poll(mbox):
    while 1:
        nums = mbox.poll()
        if nums is None:
            return

        skips = 0
        i = 0
        for num in nums:
            i += 1
            n = num.decode('utf-8')
            if track[mbox._account.name].ck_bit(int(n)):
                skips += 1
                continue
            try:
                show_notif(n, mbox)
            except:
                pass
            time.sleep(1)
        if skips == i:
            return

def loop(mbox, interval=INTERVAL):
    global SYS_EXIT

    while 1:
        if SYS_EXIT:
            break

        if VERBOSE:
            log.info("{} - {}: initiating connection".format(
                mbox._account.name,
                mbox.name))

        if mbox.status & notiflib.IMAP_Mailbox.CLOSED > 0:
            try:
                if not mbox.open():
                    time.sleep(60 - time.localtime().tm_sec)
                    continue
            except:
                if mbox.status & notiflib.IMAP_Mailbox.E_LOGIN > 0:
                    log.error('{} login error, exiting..'.format(mbox._account.name))
                    SYS_EXIT = True
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
            poll(mbox)

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

def getpass(passwd):
    if not passwd.startswith('`'):
        return passwd
    if not passwd.endswith('`'):
        return passwd
    passeval = passwd.split('`')[1]
    p = subprocess.Popen(passeval.split(), stdout=subprocess.PIPE)
    if p.returncode == 1:
        return ""
    o,e = p.communicate()
    return o.decode('utf-8')

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)
handler = logging.handlers.SysLogHandler(address = DEVLOG)
handler.setFormatter(logging.Formatter('%(module)s: %(message)s'))
log.addHandler(handler)

parser = argparse.ArgumentParser(description="IMAP Desktop Notification")
parser.add_argument("-c", "--config", help="configuration file")
parser.add_argument("-u", "--user", help="Run daemon as user")
parser.add_argument("-f", "--foreground", action='store_true', help="Run in foreground")
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

    if not args.foreground:
        daemonize()

    Notify.init("imapnotif")

    for account in accounts:
        a = notiflib.Account()
        a.server   = account["server"]
        a.port     = 143
        a.username = account["username"]
        a.password = account["password"]
        a.name     = account["name"]

        track[a.name] = Track()

        if 'ssl' in account and int(account['ssl']) == 1:
            a.ssl  = True
            a.port = 993

        i = INTERVAL
        if 'interval' in account:
            i = account['interval']

        if 'port' in account:
            a.port = account['port']

        if not 'mailboxes' in account:
            account['mailboxes'] = DEFAULT_MAILBOX

        for m in account["mailboxes"].split(","):
            mbox = notiflib.IMAP_Mailbox(a, name=m)

            try:
                if mbox.open():
                    poll(mbox)
            except:
                if mbox.status & notiflib.IMAP_Mailbox.E_LOGIN > 0:
                    log.error('{} - poll login error, account excluded!'.format(mbox._account.name))
                    continue
            MAILBOXES.append(mbox)

    if len(MAILBOXES) == 0:
        log.info("Exit! No mailbox to monitor")
        sys.exit(0)

    for M in MAILBOXES:
        Thread(target=loop, args=(M,)).start()

    GLib.unix_signal_add(GLib.PRIORITY_HIGH, signal.SIGINT, close_imap, signal.SIGINT)
    GLib.unix_signal_add(GLib.PRIORITY_HIGH, signal.SIGTERM, close_imap, signal.SIGTERM)
    try: GLib.MainLoop().run()
    except: pass
