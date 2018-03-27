#!/usr/bin/env python
''' dummy docstring '''
import json
import time
from imaplib import IMAP4_SSL

import zmq

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

    def fetch_and_parse(uids):
        ''' fetches and parses up to "mail_batch_limit" new emails '''

        result = list()

        for uid in uids:
            reply, email_data = imap_server.uid('fetch', uid, '(RFC822)')

            if reply == 'OK':
                raw_email = email_data[0][1]
                print(email_data[0][0])
                # ...(UID 10 RFC...
                # get regexp num from here
                result.append(raw_email)

        return result

    imap_server = IMAP4_SSL(address, port)              # Подключаемся.
    imap_server.login(username, password)               # Логинимся.
    imap_server.select(mailbox='INBOX', readonly=True)  # Пока только INBOX.
    # Readonly, чтобы не сбросить статус "Не прочитано".

    # Если передан UID, то читаем всё, что новее. Иначе читаем все письма.
    imap_uid_string = '{}:*'.format(uid) if uid else 'ALL'

    # Получаем tuple из статуса ответа и списка uid писем.
    reply, data = imap_server.uid('search', None, imap_uid_string)

    if reply == 'OK':
        uids_binary = data[0].split()  # Получаем строку бинарных чисел.
        len_uids_binary = len(uids_binary)

        if len_uids_binary < 2:
            if uids_binary[0] > str(uid).encode():
                return int(uids_binary[0].decode()
                           ), False, fetch_and_parse(uids_binary)

            return uid, False, False
        elif len_uids_binary > mail_batch_limit:
            if len_uids_binary > mail_total_limit:
                return int(uids_binary[-mail_total_limit:][:mail_batch_limit][-1].decode()
                           ), True, fetch_and_parse(uids_binary[-mail_total_limit:][:mail_batch_limit])

            return int(uids_binary[:mail_batch_limit][-1].decode()
                       ), True, fetch_and_parse(uids_binary[:mail_batch_limit])
        else:
            return int(uids_binary[-1].decode()
                       ), False, fetch_and_parse(uids_binary)
    else:
        return '{} returned error: {}'.format(address, reply)


REQUEST_TIMEOUT = 2500
REQUEST_RETRIES = 3
SERVER_ENDPOINT = "tcp://localhost:5555"

context = zmq.Context(1)

print("[Slave]  I've come to life! Connecting to server...")
client = context.socket(zmq.REQ)
client.connect(SERVER_ENDPOINT)

poll = zmq.Poller()
poll.register(client, zmq.POLLIN)

sequence = 0
retries_left = REQUEST_RETRIES
expect_reply = False
phase = 0
payload = None
more_mails = None
last_uid = None

while True:
    if not expect_reply:
        sequence += 1

        if phase == 0:
            words = "[Slave]  Ready to server, Master!"
        elif phase == 1:
            words = "[Slave]  I can download emails, Master!"
        elif phase == 2:
            words = "[Slave]  I need the UID of last mail I checked, Master!"
        elif phase == 3:
            payload = None

            if not more_mails:
                last_uid = last_uid or r[4]
                p = fetch_emails(imap_username, imap_password, last_uid)
            else:
                p = more_mails

            if not p[2]:
                words = "[Slave]  I've checked emails. Nothing new, Master!"
            else:
                words = "[Slave]  I've checked emails. Here is a new mail, Master!"
                payload = p[2][0].decode()

                if len(p[2][1:]) > 0:
                    more_mails = (p[0], p[1], p[2][1:])
                else:
                    last_uid = p[0]
                    more_new_mails_flag = p[1]
                    more_mails = None
        else:
            phase = 0
            time.sleep(10)

            continue
        request = json.dumps([sequence, "Slave", phase, words, payload])
        client.send_json(request)
        print(words)

        if phase == 3 and not more_mails and not more_new_mails_flag:
            print("[Slave]  Sleeping for 10 seconds.")
            time.sleep(10)

    expect_reply = True

    while expect_reply:
        socks = dict(poll.poll(REQUEST_TIMEOUT))

        if socks.get(client) == zmq.POLLIN:
            reply = client.recv_json()

            if not reply:
                break
            r = json.loads(reply)

            if int(r[0]) == sequence:
                print(r[3])
                retries_left = REQUEST_RETRIES

                if phase < 3:
                    phase = r[2] + 1
                expect_reply = False
            else:
                print("[Slave]  Malformed reply from server: %s" % reply)

        else:
            print("[Slave]  No response from server, retrying...")

            if retries_left > 0:
                retries_left -= 1

                break
            # Socket is confused. Close and remove it.
            client.setsockopt(zmq.LINGER, 0)
            client.close()
            poll.unregister(client)
            print("[Slave]  Reconnecting and resending last request...")
            # Create new connection
            client = context.socket(zmq.REQ)
            client.connect(SERVER_ENDPOINT)
            poll.register(client, zmq.POLLIN)
            retries_left = REQUEST_RETRIES
            client.send_json(request)

context.term()
