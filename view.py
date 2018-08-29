#!/usr/bin/env python3

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib

import pickle

class ViewMsg(Gtk.Window):
    '''
    View Email message.
    Initiate with ViewMsg(msg)
    where msg is email.message.Message object
    '''
    def __init__(self, msg):
        Gtk.Window.__init__(self)
        self.set_default_size(800, 300)

        builder = Gtk.Builder()
        builder.add_from_file('ui/view.glade')

        box         = builder.get_object('box')
        self.box_cc = builder.get_object('box_cc')
        subject     = builder.get_object('subject')
        _from       = builder.get_object('from')
        to          = builder.get_object('to')
        self.cc     = None
        date        = builder.get_object('date')
        text        = builder.get_object('payload')


        self.add(box)
        subject.set_text(msg["subject"].replace('\r\n', ' '))
        _from.set_text(msg["from"].replace('\r\n', ' '))
        to.set_text(msg["to"].replace('\r\n', ' '))
        date.set_text(msg["date"])
        if msg["cc"] is not None:
            self.cc     = builder.get_object('cc')
            self.cc.set_text(msg["cc"].replace('\r\n', ' '))
        buf = Gtk.TextBuffer()

        if msg.is_multipart():
            for s in msg.get_payload():
                if s.get_content_subtype() == 'plain':
                    buf.set_text(s.get_payload(decode=True).decode('utf-8', errors='ignore'))
                    break
        else:
            buf.set_text(msg.get_payload(decode=True).decode('utf-8', errors='ignore'))

        text.set_buffer(buf)

    def show_all(self):
        Gtk.Window.show_all(self)
        if self.cc is None:
            self.box_cc.hide()

if __name__ == '__main__':
    msg = pickle.load(open("msg2", "rb"))
    win = ViewMsg(msg)
    win.connect('destroy', Gtk.main_quit)
    win.show_all()

    Gtk.main()
