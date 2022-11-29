"""Backup running and scheduling."""

import croniter
import datetime
import hashlib
import humanize
import logging
import os
import shutil
import smbclient
import subprocess
import tempfile
import threading
import time
import typing

logger = logging.getLogger(__name__)
for chatty_logger in ['smbclient', 'smbprotocol', 'spnego']:
    logging.getLogger(chatty_logger).setLevel(logging.WARNING)


class Backup:
    """Class to perform backups on a set schedule."""
    BACKUP_EXTENSION = 'unf'

    def __init__(self, cron_schedule: str, udm_address: str, udm_ssh_password: str, smb_share: str, smb_username: str,
                 smb_password: str) -> None:
        if shutil.which('sshpass') is None:
            raise RuntimeError('sshpass not installed')

        try:
            self._schedule = croniter.croniter(cron_schedule, datetime.datetime.now(tz=datetime.timezone.utc))
        except croniter.CroniterBadCronError as exception:
            raise RuntimeError(f'Invalid cron schedule: {cron_schedule}') from exception
        if not udm_address:
            raise RuntimeError('Empty UDM address when trying to initialize backup')
        if not udm_ssh_password:
            raise RuntimeError('Empty UDM SSH password when trying to initialize backup')
        if not smb_share:
            raise RuntimeError('Empty SMB share when trying to initialize backup')
        if not smb_username:
            raise RuntimeError('Empty SMB username when trying to initialize backup')
        if not smb_password:
            raise RuntimeError('Empty SMB password when trying to initialize backup')

        # TODO(BDP): Eliminate sshpass if Ubiquiti ever allows installing a persistent SSH key.
        self._scp_base_args = [
            'sshpass', '-p', udm_ssh_password, 'scp', '-o', 'StrictHostKeyChecking=no',
            f'root@{udm_address}:/data/unifi/data/backup/autobackup/*.{Backup.BACKUP_EXTENSION}'
        ]  # Destination appended when performing a backup
        self._backup_timer: typing.Optional[threading.Timer] = None
        self.smb_share = smb_share
        smbclient.ClientConfig(username=smb_username, password=smb_password)

        logger.info('Initialized backup session of UDM at %s to %s', udm_address, smb_share)

    def run(self, stop_signal: threading.Event) -> None:
        if stop_signal.is_set():
            raise RuntimeError('Stop signal already set when trying to run backup')

        logger.info('Starting backup runner')
        self.backup()
        stop_signal.wait()
        logger.info('Stopping backup runner')
        if self._backup_timer is not None:
            self._backup_timer.cancel()

    def backup(self) -> None:
        logger.info('Performing backup')
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                subprocess.run([*self._scp_base_args, temp_dir], check=True, capture_output=True)
            except subprocess.CalledProcessError:
                logger.warning('Failed to pull backup files off UDM')
                return

            local_files = sorted(os.listdir(temp_dir))
            logger.debug('Pulled %d backup files off UDM', len(local_files))
            remote_files = sorted(smbclient.listdir(self.smb_share, f'*.{Backup.BACKUP_EXTENSION}'))
            logger.debug('SMB share contains %d backup files', len(remote_files))

            for filename in local_files:
                local_path = os.path.join(temp_dir, filename)
                remote_path = f'{self.smb_share}/{filename}'

                if filename in remote_files:
                    local_hash = hashlib.md5(open(local_path, 'rb').read()).hexdigest()  # pylint: disable=consider-using-with
                    remote_hash = hashlib.md5(smbclient.open_file(remote_path, 'rb').read()).hexdigest()
                    if local_hash == remote_hash:
                        logger.debug('MD5 hashes match (%s), so skipping file: %s', remote_hash, filename)
                        continue
                    else:
                        logger.debug('MD5 hash mismatch (local: %s, remote: %s), so overwriting file: %s', local_hash,
                                     remote_hash, filename)

                with open(local_path, 'rb') as local_file, smbclient.open_file(remote_path, 'wb') as remote_file:
                    shutil.copyfileobj(local_file, remote_file)
                    logger.debug('Backed up file: %s (%s)', filename, humanize.naturalsize(os.path.getsize(local_path)))

            leftover_remote_files = [filename for filename in remote_files if filename not in local_files]
            logger.debug('%d leftover remote files to prune', len(leftover_remote_files))
            for filename in leftover_remote_files:
                smbclient.remove(f'{self.smb_share}/{filename}')
                logger.debug('Removed remote file: %s', filename)

            logger.info('Successfully completed backup of %s files', len(local_files))

        next_backup_time = self._schedule.get_next(datetime.datetime)
        next_backup_interval = next_backup_time.timestamp() - time.time()
        self._backup_timer = threading.Timer(next_backup_interval, self.backup)
        self._backup_timer.start()
        logger.info('Next backup at: %s (in %d seconds)', next_backup_time.strftime('%Y-%m-%dT%H:%M:%SZ'),
                    next_backup_interval)
