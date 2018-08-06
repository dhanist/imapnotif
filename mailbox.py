#!/usr/bin/env python3

import imaplib, email
import select
import socket
import time

DEFAULT_IDLE_TIMEOUT = 5 # idle timeout in minutes
DEFAULT_FOLDER       = 'INBOX'

class Mailbox:
    """
    Mailbox class

    Instantiate with Mailbox(Account(), [name=folder_name])

    Params:
        Account is instance of Account class
    """
    E_NETWORK    = 0x001
    E_LOGIN      = 0x002
    E_SELECT     = 0x004
    CLOSED       = 0x008
    FETCH_HEADER = 0x010
    IDLE         = 0x020
    IDLE_FAILED  = 0x040


    def __init__(self, acc, **kwargs):
        self._imap      = None
        self.status     = 0
        self._read_lock = 0
        self._account   = acc
        self._tag       = None
        self.name       = kwargs.get('name')

    def open(self):
        """
        Initiate connection to server, login, and select folder.

        Returns:
            bool: True if successful, False if cannot select folder

        """
        self._read_lock &= 0
        self.status &= 0
        self.status |= self.CLOSED

        mbox = self.name
        if self.name is None:
            mbox = DEFAULT_FOLDER

        try:
            if self._account.ssl:
                self._imap = imaplib.IMAP4_SSL(self._account.server)
            else:
                self._imap = imaplib.IMAP4(self._account.server)
        except:
            self.status |= self.E_NETWORK
            raise

        if not isinstance(self._imap, imaplib.IMAP4_SSL):
            if 'STARTTLS' in self._imap.capabilities:
                self._imap.starttls()

        try: self._imap.login(
                self._account.username,
                self._account.password
            )
        except:
            self.status |= self.E_LOGIN
            raise

        retval = self._imap.select(mbox)
        if retval[0] == 'NO':
           self.status |= self.E_SELECT
           self._imap.logout()
           return False

        self._tag = self._imap._new_tag()
        self.status &= ~self.CLOSED
        return True

    def fetch(self, num, flag = 0):
        """
        Download message from server.

        Params:
            num (str): message index to be downloaded
            flag (int, optional): set with Mailbox.FETCH_HEADER to download header only

        Returns:
            Instance of email.message.Message if succeed or None otherwise
        """

        if self.status & self.IDLE > 0:
            if not self._send_done():
                raise ValueError('Mailbox is idle, cannot fetch')

        msg_parts = '(BODY.PEEK[HEADER.FIELDS (FROM DATE SUBJECT)])'
        if flag & self.FETCH_HEADER == 0:
            msg_parts = '(RFC822)'

        try:
            t, data = self._imap.fetch(num, msg_parts)
            if not t == 'OK':
                return None

            msg = email.message_from_bytes(data[0][1])
            return msg
        except: raise

    def poll(self):
        """
        Search unread emails from folder

        Returns:
            returns list [] containing message numbers or None if error
        """
        try:
            t, data = self._imap.search(None, 'UNSEEN')
            if not t == 'OK':
                return None

            return data[0].split()
        except:
            raise

    def idle(self, timeout=None):
        """
        Sending IDLE command to server and waiting for response.

        Params:
            timeout (int, optional): idle timeout in minutes, default is
            DEFAULT_IDLE_TIMEOUT

        Returns:
            decoded bytes string read from socket or None if timeout reached.

        Raises:
            IOError: Socket error
            EOFError: Socket closed by remote host
        """

        if self.status & self.IDLE == 0:
            try:
                if not self._send_idle():
                    self.status |= self.IDLE_FAILED
                    return None
            except:
                self.status |= self.IDLE_FAILED
                return None

        if timeout is None or timeout == 0:
            timeout = DEFAULT_IDLE_TIMEOUT

        if not isinstance(timeout, int):
            raise ValueError('timeout value is not an integer')

        timer = 0
        while timer < 60 * timeout:
            if self.status & self.CLOSED > 0:
                raise IOError('Socket error')
            if self.status & self.IDLE == 0:
                return None
            try:
                data = self._read_response('any', 1)
            except TimeoutError:
                timer += 1
                continue
            except Exception:
                self.status |= self.CLOSED
                raise

            return data

        if self._send_done():
            self.status &= ~self.IDLE
        else:
            self.status |= self.IDLE_FAILED
        return None

    def _send_idle(self):
        # -- imaplib doesn't support idle command --
        # send command idle to server
        # returns True if idle confirmed by remote server and False when failed
        # Exception raised when socket operation error

        if self.status & self.IDLE > 0:
            return True

        tag = self._imap._new_tag()
        try:
            self._imap.sock.send(bytes('{} IDLE\r\n'.format(tag), 'utf-8'))
            if self._read_response('idling', 10) is not None:
                self.status |= self.IDLE
                return True
        except:
            self.status |= self.CLOSED
            raise

        self.status |= self.CLOSED
        return False

    def _read_response(self, what, timeout=10):
        # read bytes on socket and search what from response
        # Returns decoded bytes string containing what or None if not match
        # TimeoutError exception raised when socket operation timeout
        # BufferError exception raised when socket closed

        self._read_lock <<= 1
        self._read_lock |= 1
        read_id = self._read_lock
        locked = False

        resp = None
        timer = 0
        while timer < timeout:
            locked = False
            sock = select.select([self._imap.sock], [], [], 1)
            if len(sock[0]) == 0:
                if resp is not None:
                    self._read_lock >>= 1
                    return None

                timer += 1
                continue

            while self._read_lock != read_id:
                if not locked:
                    locked = True

            if locked:
                continue

            resp = self._imap.file.readline()
            if len(resp) == 0:
                self._read_lock >>= 1
                raise BufferError("Connection terminated by remote host")

            data = resp.decode("utf-8").lower()
            if what == 'any':
                self._read_lock >>= 1
                return data
            if data.find(what.lower()) != -1:
                self._read_lock >>= 1
                return data

        self._read_lock >>= 1
        raise TimeoutError("socket timeout")

    def _send_done(self):
        # send DONE command to server.
        # returns True if succeed or False otherwise
        if self.status & self.IDLE == 0:
            return True
        try:
            self._imap.sock.send(bytes('DONE\r\n', 'utf-8'))
            if self._read_response('idle', 10) is not None:
                self.status &= ~self.IDLE
                self._tag = self._imap._new_tag()
                return True
        except:
            self.status |= self.CLOSED
            raise

        self.status |= self.CLOSED
        return False

    def _send_noop(self):
        # send NOOP command to server.
        # We need to be able to read response from socket after
        # issuing command so we don't use imaplib's noop method
        # returns True if succeed or False otherwise

        try:
            self._imap.sock.send(bytes('{} NOOP\r\n'.format(self._tag), 'utf-8'))
            if self._read_response('any', 10) is not None:
                return True
        except:
            self.status |= self.CLOSED
            raise

        return False

    def mark_read(self, num):
        """
        Add flag \Seen to selected message index

        Params:
            num (int): message number

        Returns:
            bool: True if successful or False if failed
        """

        if self._tag is None:
            self._tag = self._imap._new_tag()
        data = bytes("{} STORE {} +FLAGS \\Seen\r\n".format(self._tag, num), 'utf-8')
        try:
            if self.status & self.IDLE > 0:
                self._send_done()
            self._imap.sock.sendall(data)
            if self._read_response('any', 10) is not None:
                return True
        except:
            self.status |= self.CLOSED
            raise

        return False

    def close(self):
        """
        Attempt to gracefully closing selected mailbox and logout.
        On exit, this method sets status with Mailbox.CLOSED so other
        methods won't read from socket.
        Mailbox.idle will exit if this flag set.
        """

        sock_alive = False
        if self.status & self.IDLE > 0:
            sock_alive = self._send_done()
        else:
            sock_alive = self._send_noop()

        self.status |= self.CLOSED

        try:
            if sock_alive:
                self._imap.close()
                self._imap.logout()
            else:
                self._imap.sock.shutdown(socket.SHUT_RDWR)
                self._imap.file.close()
        except: pass

class Account:
    def __init__(self, **kwargs):
        self.server   = kwargs.get('server')
        self.username = kwargs.get('user')
        self.password = kwargs.get('password')
        self.ssl      = kwargs.get('ssl')
        self.name     = kwargs.get('name')
