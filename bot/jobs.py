import logging
import json
import time

from telegram import ParseMode
from telegram.ext import CallbackContext

from .qbtinstance import qb
from utils import u
from config import config

logger = logging.getLogger(__name__)


class HashesStorage:
    def __init__(self, file_path):
        self._file_path = file_path

        try:
            with open(self._file_path, 'r') as f:
                self._data = json.load(f)
        except FileNotFoundError:
            self._data = list()

    @staticmethod
    def to_list(string):
        if not isinstance(string, list):
            return [string]

        return string

    def save(self):
        with open(self._file_path, 'w+') as f:
            json.dump(self._data, f)

    def insert(self, hashes_list: [str, list]):
        hashes_list = self.to_list(hashes_list)

        for h in hashes_list:
            if h in self._data:
                continue

            self._data.append(h)

        self.save()


class Completed(HashesStorage):
    def is_new(self, torrent_hash, append=True):
        if torrent_hash not in self._data:
            if append:
                self._data.append(torrent_hash)
                self.save()

            return True
        else:
            return False


class DontNotify(HashesStorage):
    def send_notification(self, torrent_hash):
        if torrent_hash not in self._data:
            return True

        return False


completed_torrents = Completed('completed.json')
dont_notify_torrents = DontNotify('do_not_notify.json')

try:
    completed_torrents.insert([t.hash for t in qb.torrents(filter='completed')])
except ConnectionError:
    # catch the connection error raised by the OffilneClient, in case we are offline
    logger.warning('cannot register the completed torrents job: qbittorrent is not online')


@u.failwithmessage_job
def toggle_queueing(context: CallbackContext):
    logger.info('executing toggle queueing job')

    if not config.qbittorrent.get('toggle_torrents_queueing_every_night', False) or not qb.torrents_queueing:
        # do not run this job if queueing is disabled
        logger.info('torrents queueing is disabled, or disabled from config: not doing anything')
        return

    qb.disable_torrents_queueing()
    time.sleep(10)  # we need to sleep some time
    qb.enable_torrents_queueing()


@u.failwithmessage_job
def notify_completed(context: CallbackContext):
    logger.info('executing completed job')

    completed = qb.torrents(filter='completed')

    for t in completed:
        if not completed_torrents.is_new(t.hash):
            continue

        torrent = qb.torrent(t.hash)

        logger.info('completed: %s (%s)', torrent.hash, torrent.name)

        if not config.telegram.get('completed_torrents_notification', None):
            continue

        if not dont_notify_torrents.send_notification(t.hash):
            logger.info('notification disabled for torrent %s (%s)', t.hash, t.name)
            continue

        tags_lower = [tag.lower() for tag in torrent.tags]
        if config.telegram.get("no_notification_tag", None) and config.telegram.no_notification_tag.lower() in tags_lower:
            continue

        drive_free_space = u.free_space(qb.save_path)
        text = '<code>{}</code> completed ({}, free space: {})'.format(
            u.html_escape(torrent.name),
            torrent.size_pretty,
            drive_free_space
        )

        context.bot.send_message(
            chat_id=config.telegram.completed_torrents_notification,
            text=text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
            disable_notification=True
        )
