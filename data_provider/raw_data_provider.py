#!/usr/bin/env python
''' dummy docstring '''
import json
import time
from imaplib import IMAP4_SSL

import zmq
import msgpack
from imap_credentials import imap_password, imap_username


def fetch_emails(
        username,
        password,
        uid=0,
        address='imap.gmail.com',
        port=993,
        mail_batch_limit=5,    # Если писем много, то качаем пачкой.
        mail_total_limit=10):  # Временное ограничение на общее кол-во писем.
    ''' returns up to "mail_batch_limit" new emails from INBOX per run
        touches no more than "mail_total_limit" mails per multiple runs'''

    imap_server = IMAP4_SSL(address, port)              # Подключаемся.
    imap_server.login(username, password)               # Логинимся.
    # Подключаемся к INBOX
    imap_server.select(mailbox='INBOX', readonly=True)  # Пока только INBOX.
    # Readonly, чтобы не сбросить статус "Не прочитано".

    # Если передан UID, то читаем всё, что новее. Иначе читаем все письма.
    imap_uid_string = 'UID {}:*'.format(int(uid) + 1) if uid else 'ALL'

    # Получаем tuple из бинарных статуса ответа и строки uid писем.
    reply_numbers, data_numbers = imap_server.uid('search',
                                                  None,
                                                  imap_uid_string)

    if reply_numbers == 'OK':
        uid_bin = data_numbers[0].split()  # Получаем список бинарных чисел.
        len_uid_bin = len(uid_bin)
        more_mails = False
        last_uid = uid
        result = False

        if len_uid_bin <= 1:
            if uid_bin[0] > str(uid).encode():
                last_uid = uid_bin[0].decode()

            return last_uid, more_mails, result

        elif len_uid_bin > mail_batch_limit:
            more_mails = True
            if len_uid_bin > mail_total_limit:
                uid_bin = uid_bin[-mail_total_limit:]

            uid_bin = uid_bin[:mail_batch_limit]

        result = list()
        reply_email, data_email = imap_server.uid('fetch',
                                                  b','.join(uid_bin),
                                                  '(RFC822)')
        if reply_email == 'OK':
            for i in range(0, len(data_email), 2):
                imap_info = data_email[i][0].split()
                # Это строка вида: b'id (UID xx RFC822 {byte_length} ('
                uid_email = imap_info[2]        # UID
                len_email = imap_info[4][1:-1]  # {byte_length}
                raw_email = data_email[i][1]
                result.append((uid_email, len_email, raw_email))

            last_uid = uid_email.decode()
            return last_uid, more_mails, result

        return '{} returned error: {}'.format(address, reply_email)

    else:
        return '{} returned error: {}'.format(address, reply_numbers)


def zmq_slave():
    ''' ZMQ '''

    REQUEST_TIMEOUT = 2500
    REQUEST_RETRIES = 3
    SERVER_ENDPOINT = "tcp://localhost:5555"

    context = zmq.Context(1)

    # print("[Slave]  I've come to life! Connecting to server...")
    client = context.socket(zmq.REQ)
    client.connect(SERVER_ENDPOINT)

    poll = zmq.Poller()
    poll.register(client, zmq.POLLIN)

    # sequence = 0
    retries_left = REQUEST_RETRIES
    expect_reply = False
    phase = 0
    more_mails = None
    last_uid = None
    more_new_mails_flag = False

    while True:
        if not expect_reply:
            payload = None

            if phase == 1:
                if not more_mails:
                    last_uid = last_uid or reply[1]
                    last_uid, more_new_mails_flag, mails = fetch_emails(imap_username, imap_password, last_uid, 'imap.gmail.com', 993, 5, 10)
                if mails:
                    payload = mails
            request = msgpack.packb([phase, payload])
            client.send(request)
            if phase == 1 and not more_mails and not more_new_mails_flag:
                time.sleep(10)

        expect_reply = True

        while expect_reply:
            socks = dict(poll.poll(REQUEST_TIMEOUT))

            if socks.get(client) == zmq.POLLIN:
                reply = client.recv()

                if not reply:
                    break
                reply = msgpack.unpackb(reply)
                retries_left = REQUEST_RETRIES

                if phase < 1:
                    phase = reply[0] + 1
                expect_reply = False

            else:

                if retries_left > 0:
                    retries_left -= 1

                    break
                client.setsockopt(zmq.LINGER, 0)
                client.close()
                poll.unregister(client)
                client = context.socket(zmq.REQ)
                client.connect(SERVER_ENDPOINT)
                poll.register(client, zmq.POLLIN)
                retries_left = REQUEST_RETRIES
                client.send(request)

    context.term()

if __name__ == '__main__':
    zmq_slave()
