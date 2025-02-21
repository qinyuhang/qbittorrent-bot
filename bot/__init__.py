import datetime
import logging
import logging.config
import json

from .updater import updater
from .jobs import notify_completed, toggle_queueing
from .qbtinstance import qb
from config import config


def load_logging_config(file_path='logging.json'):
    with open(file_path, 'r') as f:
        logging_config = json.load(f)

    logging.config.dictConfig(logging_config)


logger = logging.getLogger(__name__)


def main():
    load_logging_config()

    updater.import_handlers(r'bot/plugins/')

    if qb.online:
        logger.info('registering jobs')
        updater.job_queue.run_repeating(notify_completed, interval=120, first=120)
        updater.job_queue.run_daily(toggle_queueing, time=datetime.time(hour=2, minute=0))

        # create the tag on startup
        if config.qbittorrent.get("added_torrents_tag", None) and config.qbittorrent.added_torrents_tag:
            qb.create_tags(config.qbittorrent.added_torrents_tag)

    updater.set_bot_commands(show_first=["quick", "active", "tostart"])
    updater.run(drop_pending_updates=True)
