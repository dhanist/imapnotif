#!/usr/bin/env python3

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib
from notiflib import IMAP_Mailbox
from threading import Thread
from bs4 import BeautifulSoup as BS4
import os, ui
from email.header import make_header, decode_header

import traceback

class ViewMsg(Gtk.Window):
    def __init__(self, account, inbox, num):
        Gtk.Window.__init__(self)
        self.set_title("View Message")
        self.set_default_size(800, 300)

        cwd = os.path.dirname(ui.__file__)
        self.builder = Gtk.Builder()
        self.builder.add_from_file(os.path.join(cwd, "view.glade"))

        box            = self.builder.get_object('box')
        self.box_cc    = self.builder.get_object('box_cc')
        self.subject   = self.builder.get_object('subject')
        self._from     = self.builder.get_object('from')
        self.to        = self.builder.get_object('to')
        self.cc        = self.builder.get_object('cc')
        self.sep_cc    = self.builder.get_object('sep_cc')
        self.date      = self.builder.get_object('date')
        self.text      = self.builder.get_object('payload')
        self.statusbar = self.builder.get_object('statusbar')

        self.add(box)
        self.buf = Gtk.TextBuffer()
        self.statusbar.push(0, "loading...")

        self._account = account
        self._num     = num
        self._inbox   = inbox

        Thread(target=self.load).start()

    def load(self):
        msg = None
        if self._account is None or self._num is None:
            return

        buf = Gtk.TextBuffer()
        try:
            self.statusbar.push(0, "connecting to {}...".format(self._account.server))
            mbox = IMAP_Mailbox(self._account, name=self._inbox)
            self.statusbar.push(0, "opening folder {}...".format(mbox.name))
            if not mbox.open():
                self.statusbar.push(0, "failed")
                return
            self.statusbar.push(0, "fetching message...")
            msg = mbox.fetch(self._num)
            if msg is None:
                self.statusbar.push(0, "fetching message failed")
                return

            self.subject.set_text(
                str(make_header(decode_header(msg.get('subject'))))
            )
            self._from.set_text(
                str(make_header(decode_header(
                    msg["from"].replace('\r\n', ' '))))
            )
            self.to.set_text(
                str(make_header(decode_header(
                    msg["to"].replace('\r\n', ' '))))
            )
            self.date.set_text(msg["date"])
            if msg["cc"] is not None:
                self.cc.set_text(msg["cc"].replace('\r\n', ' '))
                self.box_cc.show()
                self.sep_cc.show()
            buf.set_text(self.get_content(msg))
        except:
            traceback.print_exc()
            buf.set_text("Error")
        self.text.set_buffer(buf)
        self.statusbar.push(0, "disconnect from {}...".format(self._account.server))
        mbox.close()
        self.statusbar.push(0, "done")

    def get_content(self, msg):
        txt = ""
        if msg.is_multipart():
            for s in msg.walk():
                pl = s.get_payload(decode = True)
                if not pl: continue
                raw = pl.decode('utf-8', errors = 'ignore')
                if s.get_content_subtype() == 'plain':
                    txt = raw
                    break
                if s.get_content_subtype() == 'html':
                    txt = "\n".join(BS4(raw, "html.parser").stripped_strings)
                    continue
                txt = raw
            return txt

        pl = msg.get_payload(decode = True)
        if not pl: return ""

        raw = pl.decode('utf-8', errors = 'ignore')
        if msg.get_content_subtype() == 'plain':
            return raw
        if msg.get_content_subtype() == 'html':
            return "\n".join(BS4(raw, "html.parser").stripped_strings)
        return raw

    def show_all(self):
        Gtk.Window.show_all(self)
        self.box_cc.hide()
        self.sep_cc.hide()
