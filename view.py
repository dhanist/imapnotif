#!/usr/bin/env python3

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib
from notiflib import IMAP_Mailbox
from threading import Thread
from bs4 import BeautifulSoup as BS4

import traceback

class ViewMsg(Gtk.Window):
    def __init__(self, account, inbox, num):
        Gtk.Window.__init__(self)
        self.set_default_size(800, 300)

        self.builder = Gtk.Builder()
        self.builder.add_from_file('ui/view.glade')

        box          = self.builder.get_object('box')
        self.box_cc  = self.builder.get_object('box_cc')
        self.subject = self.builder.get_object('subject')
        self._from   = self.builder.get_object('from')
        self.to      = self.builder.get_object('to')
        self.cc      = self.builder.get_object('cc')
        self.sep_cc  = self.builder.get_object('sep_cc')
        self.date    = self.builder.get_object('date')
        self.text    = self.builder.get_object('payload')

        self.add(box)
        self.buf = Gtk.TextBuffer()
        self.buf.set_text("Loading...")
        self.text.set_buffer(self.buf)

        self._account = account
        self._num     = num
        self._inbox   = inbox

        Thread(target=self.load).start()

    def set_account(self, acc):
        self.account = acc
    def set_num(self, num):
        self.num = num

    def load(self):
        msg = None
        if self._account is None or self._num is None:
            return

        buf = Gtk.TextBuffer()
        try:
            mbox = IMAP_Mailbox(self._account, name=self._inbox)
            if not mbox.open():
                return
            msg = mbox.fetch(self._num)
            if msg is None:
                print("Msg is None")
                return

            self.subject.set_text(msg["subject"].replace('\r\n', ' '))
            self._from.set_text(msg["from"].replace('\r\n', ' '))
            self.to.set_text(msg["to"].replace('\r\n', ' '))
            self.date.set_text(msg["date"])
            if msg["cc"] is not None:
                self.cc.set_text(msg["cc"].replace('\r\n', ' '))
                self.box_cc.show()
                self.sep_cc.show()

            if msg.is_multipart():
                for s in msg.walk():
                    if s.get_content_subtype() == 'plain':
                        txt = s.get_payload(decode=True).decode('utf-8', errors='ignore')
                        break

            else:
                if msg.get_content_subtype() == 'html':
                    txt = "".join(BS4(
                        msg.get_payload(decode=True).decode('utf-8', errors='ignore'),
                        "html.parser").stripped_strings)
                else:
                    txt = msg.get_payload(decode=True).decode('utf-8', errors='ignore')

            buf.set_text(txt)
        except:
            traceback.print_exc()
            buf.set_text("Error")
        self.text.set_buffer(buf)


    def show_all(self):
        Gtk.Window.show_all(self)
        self.box_cc.hide()
        self.sep_cc.hide()
