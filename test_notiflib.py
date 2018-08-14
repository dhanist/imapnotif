#!/usr/bin/env python3
import notiflib
import unittest
from unittest import mock
import imaplib, email.message
import sys, time
import socket

resp = [(b'30612 (RFC822 {2810}', b'Return-Path: <engineer-bounces@transkon.net.id>\r\nReceived: from hoth.transkon.net.id\r\n\tby 6797ffe204e0 (Dovecot) with LMTP id U0WpEPfaZlv3PwAAzar5/g\r\n\t; Sun, 05 Aug 2018 19:09:43 +0800\r\nReceived: from [175.184.251.247] (localhost [IPv6:::1])\r\n\tby hoth.transkon.net.id (Postfix) with ESMTP id B63484A3C13;\r\n\tSun, 5 Aug 2018 19:09:42 +0800 (WITA)\r\nX-Original-To: engineer@transkon.net.id\r\nDelivered-To: engineer@mx0.transkon.net.id\r\nReceived: from localhost (unknown [IPv6:2402:e180:0:130::a])\r\n by hoth.transkon.net.id (Postfix) with ESMTPA id 652024A3C8A\r\n for <engineer@transkon.net.id>; Sun,  5 Aug 2018 19:09:41 +0800 (WITA)\r\nDKIM-Signature: v=1; a=rsa-sha256; c=simple/simple; d=transkon.net.id; s=mx;\r\n t=1533467381; bh=pkEGEjyMOdEG0ItrhgMTK2uKLILf5htWgRGLTmNt2AI=;\r\n h=From:To:Reply-To:Subject:Date:From;\r\n b=ERTI6e8Kwoleoy+B5q9xXbLVteHmSpWnObfgnFgdQpCFKG3wI4RpllTxByTpdtWY6\r\n cjqN4DH/ZUpBjGAFUAHsOdck3tR9hrOf0grh9VLD0GkiPI3mc35u2S0CSysFFuX5nq\r\n KFM15VC1/otCdYr9mz4BzlMyqeL3yLsArAEhiagY=\r\nFrom:Transkon-Net ID Monitoring System<monitoring@transkon.net.id>\r\nTo: engineer@transkon.net.id\r\nDate: Sun, 05 Aug 2018 19:09:41 +0800\r\nSubject: [Engineer] Host Minamas Sebamban.radio (36.89.14.155) PROBLEM\r\nX-BeenThere: engineer@transkon.net.id\r\nX-Mailman-Version: 2.1.18\r\nPrecedence: list\r\nList-Id: <engineer.transkon.net.id>\r\nList-Unsubscribe: <http://list.transkon.net.id/cgi-bin/mailman/options/engineer>, \r\n <mailto:engineer-request@transkon.net.id?subject=unsubscribe>\r\nList-Post: <mailto:engineer@transkon.net.id>\r\nList-Help: <mailto:engineer-request@transkon.net.id?subject=help>\r\nList-Subscribe: <http://list.transkon.net.id/cgi-bin/mailman/listinfo/engineer>, \r\n <mailto:engineer-request@transkon.net.id?subject=subscribe>\r\nReply-To: engineer@transkon.net.id\r\nMIME-Version: 1.0\r\nContent-Type: text/plain; charset=utf-8\r\nContent-Transfer-Encoding: base64\r\nErrors-To: engineer-bounces@transkon.net.id\r\nSender: Engineer <engineer-bounces@transkon.net.id>\r\nMessage-Id: <20180805110942.B63484A3C13@hoth.transkon.net.id>\r\nX-Spam-Status: No, score=-2.9 required=3.0 tests=ALL_TRUSTED,BAYES_00,\r\n\tT_DKIM_INVALID autolearn=ham autolearn_force=no version=3.4.0\r\nX-Spam-Checker-Version: SpamAssassin 3.4.0 (2014-02-07) on 6797ffe204e0\r\n\r\nKioqIERPIE5PVCBSRVBMWSAtLSBUaGlzIGlzIG5vdGlmaWNhdGlvbiBmcm9tIG1vbml0b3Jpbmcg\r\nc2VydmVyICoqKgoKTm90aWZpY2F0aW9uIFR5cGUJOiBQUk9CTEVNCkhvc3QJCQk6IE1pbmFtYXMg\r\nU2ViYW1iYW4ucmFkaW8KSVAgQWRkcmVzcwkJOiAzNi44OS4xNC4xNTUKU3RhdGUJCQk6IERPV04K\r\nRGF0ZS9UaW1lCQk6IFN1biBBdWcgNSAxOTowOTo0MSBXSVRBIDIwMTgKSW5mbwkJCTogUElORyBD\r\nUklUSUNBTCAtIFBhY2tldCBsb3NzID0gMTAwJQpfX19fX19fX19fX19fX19fX19fX19fX19fX19f\r\nX19fX19fX19fX19fX19fX19fXwpFbmdpbmVlciBtYWlsaW5nIGxpc3QKRW5naW5lZXJAdHJhbnNr\r\nb24ubmV0LmlkCmh0dHA6Ly9saXN0LnRyYW5za29uLm5ldC5pZC9jZ2ktYmluL21haWxtYW4vbGlz\r\ndGluZm8vZW5naW5lZXI=\r\n'), b')']

class TestIMAP_Mailbox(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(TestIMAP_Mailbox, self).__init__(*args, **kwargs)
        self.acc = notiflib.Account()
        self.acc.name     = "Test"
        self.acc.username = 'test@test.com'
        self.acc.server   = 'imap.test.com'
        self.acc.password = 'somepass'

    def _null(self):
        pass
    def _raise(self, exc):
        raise exc

    @mock.patch('notiflib.imaplib.IMAP4')
    def test_open(self, IMAP4):
        mbox = notiflib.IMAP_Mailbox(self.acc)

        # err resource unavailable
        IMAP4.side_effect = IOError('Resource Unavailable')
        self.assertRaises(IOError)

        # err login
        IMAP4.side_effect = None
        imap = IMAP4()
        imap.login.side_effect = ValueError('Login error')
        self.assertRaises(ValueError)

        # err select
        imap.login.side_effect = None
        imap.select.return_value = ('NO', [b'IMAP_Mailbox doesn\'t exist'])
        self.assertTrue(mbox.open() == False and mbox.status & notiflib.IMAP_Mailbox.E_SELECT > 0)

        # OK
        imap.select.return_value = ('OK', [b'SELECTED'])
        self.assertTrue(mbox.open())

        self.assertTrue(mbox._tag is not None)

    @mock.patch('notiflib.imaplib.IMAP4')
    def test_fetch(self, IMAP4):
        imap = IMAP4()

        mbox = notiflib.IMAP_Mailbox(self.acc)
        mbox.open()

        imap.fetch.return_value = ('OK', resp)
        mbox.status |= notiflib.IMAP_Mailbox.IDLE
        mbox._send_done = lambda: False
        with self.assertRaises(ValueError):
            data = mbox.fetch('1234', notiflib.IMAP_Mailbox.FETCH_HEADER)

        mbox.status &= ~notiflib.IMAP_Mailbox.IDLE
        data = mbox.fetch('1234', notiflib.IMAP_Mailbox.FETCH_HEADER)
        self.assertTrue(isinstance(data, email.message.Message))

        imap.fetch.side_effect = IOError('blah')
        with self.assertRaises(IOError):
            data = mbox.fetch('1234')

    @mock.patch('notiflib.imaplib.IMAP4')
    def test_poll(self, IMAP4):
        imap = IMAP4()
        mbox = notiflib.IMAP_Mailbox(self.acc)
        mbox.open()

        imap.search.return_value = ('BAD', [b''])
        retval = mbox.poll()
        self.assertTrue(retval == None)

        imap.search.return_value = ('OK', [b''])
        retval = mbox.poll()
        self.assertTrue(len(retval) == 0)

        imap.search.return_value = ('OK', [b'1234 4321'])
        retval = mbox.poll()
        self.assertTrue(len(retval) == 2)

        imap.search.side_effect = ValueError('Blah')
        with self.assertRaises(ValueError):
            mbox.poll()

    @mock.patch('notiflib.imaplib.IMAP4')
    @mock.patch('notiflib.select')
    @mock.patch('notiflib.IMAP_Mailbox._read_response')
    def test_idle(self, resp, Select, IMAP4):
        imap = IMAP4()
        mbox = notiflib.IMAP_Mailbox(self.acc)
        mbox.open()

        mbox.status &= ~notiflib.IMAP_Mailbox.IDLE
        mbox._send_idle = lambda: False
        self.assertTrue(mbox.idle() == None)

        mbox._send_idle = lambda: True
        mbox._send_done = lambda: True

        mbox.status |= notiflib.IMAP_Mailbox.IDLE
        resp.return_value = '* 1234 exists'
        self.assertTrue(mbox.idle() == '* 1234 exists')

        resp.side_effect = BufferError("socket close")
        with self.assertRaises(BufferError):
            mbox.idle()

        mbox.status &= ~notiflib.IMAP_Mailbox.CLOSED
        resp.side_effect = TimeoutError("socket timeout")
        self.assertFalse(mbox.idle())

    @mock.patch('notiflib.imaplib.IMAP4')
    @mock.patch('notiflib.IMAP_Mailbox._read_response')
    def test_send_idle(self, resp, IMAP4):
        imap = IMAP4()
        mbox = notiflib.IMAP_Mailbox(self.acc)
        mbox.open()

        mbox.status &= ~notiflib.IMAP_Mailbox.IDLE
        resp.return_value = b'OK idling\r\n'
        self.assertTrue(mbox._send_idle())

        mbox.status &= ~notiflib.IMAP_Mailbox.IDLE
        resp.side_effect = TimeoutError("blah")
        self.assertFalse(mbox._send_idle())

        mbox.status &= ~notiflib.IMAP_Mailbox.IDLE
        resp.side_effect = Exception("blah")
        self.assertRaises(IOError)

    @mock.patch('notiflib.imaplib.IMAP4')
    def test_read_response(self, IMAP4):
        imap = IMAP4()
        mbox = notiflib.IMAP_Mailbox(self.acc)
        mbox.open()

        s_notiflib, s_test = socket.socketpair()
        mbox._imap.sock = s_notiflib

        # timeout
        with self.assertRaises(TimeoutError):
            mbox._read_response('blah', timeout=2)

        # match
        s_test.send(bytes('* 1234 EXISTS\r\n', 'utf-8'))
        self.assertTrue(mbox._read_response() == '* 1234 exists')
        s_test.send(bytes('TAG IDLE Completed\r\n', 'utf-8'))
        self.assertTrue(mbox._read_response('idle', tag='TAG') == 'tag idle completed')

        # half closed socket
        s_test.shutdown(socket.SHUT_RDWR)
        with self.assertRaises(BufferError):
            mbox._read_response()

        s_notiflib.close()
        s_test.close()

    @mock.patch('notiflib.imaplib.IMAP4')
    @mock.patch('notiflib.IMAP_Mailbox._read_response')
    def test_send_done(self, resp, IMAP4):
        imap = IMAP4()
        mbox = notiflib.IMAP_Mailbox(self.acc)
        mbox.open()

        self.assertTrue(mbox._send_done())

        mbox.status |= notiflib.IMAP_Mailbox.IDLE
        imap.sock.send.side_effect = IOError("blah")
        with self.assertRaises(IOError):
            mbox._send_done()
        self.assertTrue(mbox.status & notiflib.IMAP_Mailbox.CLOSED > 0)
        imap.sock.send.side_effect = None

        resp.return_value = "blah"
        self.assertTrue(mbox._send_done())
        arg, kwarg = imap.sock.send.call_args_list[0]
        self.assertTrue(arg[0] == b'DONE\r\n')

        mbox.status |= notiflib.IMAP_Mailbox.IDLE
        resp.side_effect = TimeoutError("blah")
        self.assertFalse(mbox._send_done())

    @mock.patch('notiflib.imaplib.IMAP4')
    @mock.patch('notiflib.IMAP_Mailbox._read_response')
    def test_send_noop(self, resp, IMAP4):
        imap = IMAP4()
        mbox = notiflib.IMAP_Mailbox(self.acc)
        mbox.open()

        mbox._tag = "TAG"

        resp.return_value = "blah"
        self.assertTrue(mbox._send_noop())

        resp.side_effect = TimeoutError("blah")
        self.assertFalse(mbox._send_noop())

        imap.sock.send.side_effect = BrokenPipeError("blah")
        with self.assertRaises(BrokenPipeError):
            mbox._send_noop()

    @mock.patch('notiflib.imaplib.IMAP4')
    def test_close(self, IMAP4):
        imap = IMAP4()
        mbox = notiflib.IMAP_Mailbox(self.acc)
        mbox.open()

        mbox.status |= notiflib.IMAP_Mailbox.IDLE
        mbox._send_done = lambda: True
        mbox.close()
        self.assertTrue(imap.close.called)

        mbox.status &= ~notiflib.IMAP_Mailbox.IDLE
        mbox._send_noop = lambda: False
        mbox.close()
        self.assertTrue(imap.sock.shutdown.called)
        self.assertTrue(mbox.status & notiflib.IMAP_Mailbox.CLOSED > 0)

    @mock.patch('notiflib.imaplib.IMAP4')
    @mock.patch('notiflib.IMAP_Mailbox._read_response')
    def test_mark_read(self, resp, IMAP4):
        imap = IMAP4()
        mbox = notiflib.IMAP_Mailbox(self.acc)
        mbox.open()

        imap.sock.sendall.side_effect = IOError("poll error")
        with self.assertRaises(IOError):
            mbox.mark_read("1234")

        imap.sock.sendall.side_effect = None
        resp.return_value = "blah"
        self.assertTrue(mbox.mark_read("1234"))

if __name__ == '__main__':
    unittest.main(verbosity=2)
