"""Moves TeamSpeak clients to an AFK channel after they have been idle for a while,
and moves them back to their previous channel once they become active again.

Talks to the server over SSH ServerQuery. Configured through environment variables.
"""
import os
import re
import time

import paramiko

HOST = os.environ.get("TS_HOST", "teamspeak")
PORT = int(os.environ.get("TS_PORT", "10022"))
USER = os.environ.get("TS_USER", "serveradmin")
PASSWORD = os.environ["TS_PASSWORD"]
SERVER_ID = os.environ.get("TS_SERVER_ID", "1")
AFK_CHANNEL = os.environ.get("AFK_CHANNEL", "AFK").strip().lower()
IDLE_SECONDS = int(float(os.environ.get("IDLE_MINUTES", "5")) * 60)
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", "30"))
RETURN_BACK = os.environ.get("RETURN_BACK", "true").strip().lower() in ("1", "true", "yes")

ERROR_RE = re.compile(r"error id=(\d+) msg=(\S*)")
ESCAPES = {"\\s": " ", "\\p": "|", "\\/": "/", "\\\\": "\\", "\\n": "\n", "\\r": "\r", "\\t": "\t"}

# clid -> channel id the client was in before being moved to AFK
moved = {}


def log(msg):
    print(time.strftime("%Y-%m-%d %H:%M:%S"), msg, flush=True)


def unescape(value):
    return re.sub(r"\\[spn/\\rt]", lambda m: ESCAPES[m.group(0)], value)


def parse(data):
    rows = []
    for item in data.split("|"):
        row = {}
        for pair in item.split():
            key, _, value = pair.partition("=")
            row[key] = unescape(value)
        if row:
            rows.append(row)
    return rows


class Query:
    def __init__(self):
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.client.connect(HOST, port=PORT, username=USER, password=PASSWORD,
                            look_for_keys=False, allow_agent=False, timeout=15)
        self.chan = self.client.invoke_shell()
        self.chan.settimeout(15)
        time.sleep(1)
        while self.chan.recv_ready():
            self.chan.recv(65536)  # drop the greeting banner

    def run(self, command):
        self.chan.send(command + "\n")
        buf = ""
        while True:
            chunk = self.chan.recv(65536).decode("utf-8", "replace")
            if not chunk:
                raise ConnectionError("query connection closed")
            buf += chunk
            match = ERROR_RE.search(buf)
            if match:
                break
        if match.group(1) != "0":
            raise RuntimeError(f"{command!r} failed: {match.group(0)}")
        return buf[:match.start()].strip()

    def close(self):
        self.client.close()


def find_channel(query):
    for row in parse(query.run("channellist")):
        if row.get("channel_name", "").strip(": ").lower() == AFK_CHANNEL:
            return row["cid"]
    raise RuntimeError(f"channel {AFK_CHANNEL!r} not found")


def move_back(query, row, afk_cid):
    """Move an active client from AFK back to where it was, if that channel still exists."""
    target = moved.pop(row["clid"])
    try:
        query.run(f"clientmove clid={row['clid']} cid={target}")
        log(f"moved {row.get('client_nickname')} back to channel {target}")
    except RuntimeError as exc:
        log(f"could not move {row.get('client_nickname')} back: {exc}")


def sweep(query, afk_cid):
    clients = [row for row in parse(query.run("clientlist -times"))
               if row.get("client_type") == "0"]
    online = {row["clid"] for row in clients}

    for clid in list(moved):  # forget clients that disconnected
        if clid not in online:
            del moved[clid]

    for row in clients:
        clid = row["clid"]
        idle = int(row.get("client_idle_time", "0")) // 1000

        if row.get("cid") == afk_cid:
            if RETURN_BACK and clid in moved and idle < IDLE_SECONDS:
                move_back(query, row, afk_cid)
            continue

        moved.pop(clid, None)  # client left AFK on its own
        if idle >= IDLE_SECONDS:
            query.run(f"clientmove clid={clid} cid={afk_cid}")
            moved[clid] = row["cid"]
            log(f"moved {row.get('client_nickname')} to AFK after {idle // 60} min idle")


def main():
    while True:
        try:
            query = Query()
            query.run(f"use {SERVER_ID}")
            afk_cid = find_channel(query)
            log(f"connected, AFK channel id {afk_cid}, limit {IDLE_SECONDS // 60} min")
            while True:
                sweep(query, afk_cid)
                time.sleep(CHECK_INTERVAL)
        except Exception as exc:
            log(f"error: {exc}; retrying in 30s")
            time.sleep(30)


if __name__ == "__main__":
    main()
