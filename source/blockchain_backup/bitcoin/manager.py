'''
    Utilities to manage bitcoin core.

    Copyright 2018-2021 DeNova
    Last modified: 2021-07-17
'''

from blockchain_backup.bitcoin import constants, core_utils
from blockchain_backup.bitcoin.backup_utils import get_next_backup_in, need_to_backup
from blockchain_backup.bitcoin.gen_utils import get_ok_button, set_action_update
from blockchain_backup.bitcoin.handle_cli import get_blockchain_info, update_latest_state
from blockchain_backup.bitcoin.preferences import get_bitcoin_dirs
from blockchain_backup.bitcoin.state import get_last_known_block, set_last_known_block, set_last_block_time

from denova.python.log import Log


class BitcoinManager():
    '''
        Manage bitcoin's blockchain.
    '''

    def __init__(self, log_name, use_fresh_debug_log=True):
        '''
            Initialize bitcoin core manager.

            >>> manager = BitcoinManager('blockchain_backup.bitcoin.manager.log')
            >>> manager is not None
            True
        '''

        self.log = Log(filename=log_name)

        self.bin_dir, self.data_dir = get_bitcoin_dirs()
        if use_fresh_debug_log:
            self.debug_log = core_utils.get_fresh_debug_log(self.data_dir)
        else:
            self.debug_log = core_utils.get_debug_log_name(self.data_dir)

        self.total_blocks_needed = None
        self.new_blocks_found = False

        self.last_progress_update = None
        self.last_notice_update = None
        self.last_subnotice_update = None
        self.last_header_update = None

        # give system time to connect
        ##sleep(5)

    def get_current_block(self, show_progress=True, show_next_backup_time=True):
        '''
            Get the current block and update the progress, if appropriate.

            >>> # this test always returns -1 because bitcoin is not running
            >>> # the unittest exercise this code more thoroughly
            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> test_utils.init_database()
            >>> manager = BitcoinManager('blockchain_backup.bitcoin.manager.log')
            >>> manager.get_current_block()
            -1
        '''

        blockchain_info = get_blockchain_info(self.bin_dir,
                                              self.data_dir,
                                              progress_func=self.update_progress)
        return self.update_blockchain_info(
          blockchain_info, show_progress=show_progress,
          show_next_backup_time=show_next_backup_time)

    def update_blockchain_info(self, blockchain_info, show_progress=True, show_next_backup_time=True):
        '''
            Give the user feedback and get the current block.

            >>> from json import dumps
            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> test_utils.init_database()
            >>> manager = BitcoinManager('blockchain_backup.bitcoin.manager.log')
            >>> blockchain_info = {
            ...                    'chain': "main",
            ...                    'blocks': 569083,
            ...                    'headers': 569083,
            ...                    'mediantime': 1553711097,
            ...                    'warnings': "",
            ...                   }
            >>> manager.update_blockchain_info(blockchain_info)
            569083
            >>> manager.update_blockchain_info(blockchain_info, show_progress=False)
            569083
            >>> manager.update_blockchain_info(blockchain_info, show_next_backup_time=False)
            569083
            >>> blockchain_info = {
            ...                    "chain": "main",
            ...                    "blocks": 569167,
            ...                    "headers": 569167,
            ...                    "mediantime": 1553711097,
            ...                    "warnings": "Something's wrong"
            ...                   }
            >>> manager.update_blockchain_info(blockchain_info)
            569167
            >>> blockchain_info = None
            >>> manager.update_blockchain_info(blockchain_info)
            -1
            >>> blockchain_info = -1
            >>> manager.update_blockchain_info(blockchain_info)
            -1
        '''

        if blockchain_info is None or blockchain_info == -1:
            current_block = -1
        else:
            if 'warnings' in blockchain_info:
                warnings = blockchain_info['warnings']
            else:
                warnings = None

            if warnings:
                current_block = int(blockchain_info['blocks'])
                self.update_progress(warnings)
            else:
                current_block, progress = self.format_blockchain_update(
                  blockchain_info, show_next_backup_time=show_next_backup_time)
                if show_progress and progress is not None:
                    self.update_progress(progress)

        return current_block

    def format_blockchain_update(self, blockchain_info, show_next_backup_time=True):
        '''
            Format the update to the blockchain.

            >>> manager = BitcoinManager('blockchain_backup.bitcoin.manager.log')
            >>> manager.data_dir = '/tmp/bitcoin/data/testnet3'
            >>> blockchain_info = {
            ...                    "chain": "main",
            ...                    "blocks": 569060,
            ...                    "headers": 569164,
            ...                    "bestblockhash": "0000000000000000001ded7310261af91403b97bf02e227b26cccc35bde3eccd",
            ...                    "difficulty": 6379265451411.053,
            ...                    "mediantime": 1553711097,
            ...                    "warnings": ""
            ...                   }
            >>> current_block, progress = manager.format_blockchain_update(
            ...   blockchain_info, show_next_backup_time=False)
            >>> current_block == 569060
            True
            >>> progress.find('Next backup in:') > 0
            False
            >>> current_block, progress = manager.format_blockchain_update(blockchain_info)
            >>> current_block == 569060
            True
            >>> len(progress) > 0
            True
            >>> blockchain_info = {
            ...                    "chain": "main",
            ...                    "blocks": 2,
            ...                    "headers": 0,
            ...                    "mediantime": 1553711097,
            ...                    "warnings": ""
            ...                   }
            >>> current_blocks, progress = manager.format_blockchain_update(blockchain_info)
            >>> current_blocks
            2
            >>> len(progress) > 0
            True
        '''

        progress = None

        current_block, remaining_blocks, recent_confirmation = update_latest_state(blockchain_info)
        if current_block >= 0:
            # report something more meaningful than -1
            if remaining_blocks < 0:
                remaining_blocks = 'Unknown'

            rows = []
            rows.append(self.format_row('Number of blocks to update', remaining_blocks))
            rows.append(self.format_row('Most recent confirmation',
                                        recent_confirmation,
                                        title='Most recent transaction confirmed on your Bitcoin node'))

            if show_next_backup_time:
                status = get_next_backup_in()
                if status is not None:
                    rows.append(self.format_row('Next backup in', status))

            elif current_block > 0:
                need_backup = need_to_backup(self.data_dir, current_block)
                if need_backup and core_utils.is_bitcoin_qt_running():
                    rows.append(self.format_row('<font color="red">Backup needed</font>',
                    'Stop Bitcoin-QT as soon as possible to protect your blockchain. The backup will start automatically.'))

            progress = f"<table cellspacing=\"5\">{''.join(rows)}</table>"

        return current_block, progress

    def format_row(self, label, value, title=None):
        '''
            Format a row in a 2 column table.

            >>> manager = BitcoinManager('blockchain_backup.bitcoin.manager.log')
            >>> manager.format_row('Test', 100)
            '<tr><td><strong>Test:&nbsp;&nbsp;</strong></td><td valign="bottom">100</td></tr>'
            >>> manager.format_row('Another test', 59, title='Help text')
            '<tr><td><span title="Help text"><strong>Another test:&nbsp;&nbsp;</strong></span></td><td><span title="Help text">59</span></td></tr>'
        '''

        FORMAT1 = '<tr><td><strong>{}:&nbsp;&nbsp;</strong></td><td valign="bottom">{}</td></tr>'
        FORMAT2 = '<tr><td><span title="{}"><strong>{}:&nbsp;&nbsp;</strong></span></td><td><span title="{}">{}</span></td></tr>'

        if title is None:
            row = FORMAT1.format(label, value)
        else:
            row = FORMAT2.format(title, label, title, value)

        return row

    def get_last_progress_update(self):
        '''
            Get the last progress message.

            >>> manager = BitcoinManager('blockchain_backup.bitcoin.manager.log')
            >>> manager.get_last_progress_update()
        '''

        return self.last_progress_update

    def notify_close_window(self, notice=constants.CLOSE_WINDOW_NOW):
        '''
            Notify user we stopped activity successfully.

            >>> manager = BitcoinManager('blockchain_backup.bitcoin.manager.log')
            >>> manager.notify_close_window()
            >>> manager.notify_close_window(notice='Serious error')
        '''

        notice_and_button = f'{notice}{get_ok_button()}'
        self.update_notice(notice_and_button)
        self.update_alert_color('green')
        self.update_menu(constants.ENABLE_ITEM)

    def notify_done(self, notice=constants.CLOSE_WINDOW_NOW):
        '''
            Notify user and clear progress.

            >>> manager = BitcoinManager('blockchain_backup.bitcoin.manager.log')
            >>> manager.notify_done()
            >>> manager.notify_done(notice='Serious error')
        '''

        self.notify_close_window(notice=notice)
        self.update_progress('&nbsp;')

    def update_header(self, text):
        '''
            Send an updated header to the user.

            >>> manager = BitcoinManager('blockchain_backup.bitcoin.manager.log')
            >>> manager.update_header('Test Header')
        '''

        if self.last_header_update != text:
            self.last_header_update = text
            html = text.replace('\n', '<br/>')
            set_action_update('header-id', html)
            self.log(f'header: {text.strip()}')

    def update_notice(self, text):
        '''
            Send a notice to the user.

            >>> manager = BitcoinManager('blockchain_backup.bitcoin.manager.log')
            >>> manager.update_notice('Warning')
        '''

        if self.last_notice_update != text:
            self.last_notice_update = text
            html = text.replace('\n', '<br/>')
            set_action_update('notice-id', html)
            self.log(f'notice: {text.strip()}')

    def update_subnotice(self, text):
        '''
            Send a sub-notice to the user.

            >>> manager = BitcoinManager('blockchain_backup.bitcoin.manager.log')
            >>> manager.update_subnotice('More info')
        '''

        if self.last_subnotice_update != text:
            self.last_subnotice_update = text
            html = text.replace('\n', '<br/>')
            set_action_update('subnotice-id', html)
            self.log(f'subnotice: {text.strip()}')

    def update_progress(self, text):
        '''
            Send progress update to user.

            >>> manager = BitcoinManager('blockchain_backup.bitcoin.manager.log')
            >>> manager.update_progress('Details')
        '''

        if self.last_progress_update != text:
            self.last_progress_update = text
            html = text.replace('\n', '<br/>')
            set_action_update('progress-id', html)

    def update_alert_color(self, color):
        '''
            Change the color of the alert box.

            >>> manager = BitcoinManager('blockchain_backup.bitcoin.manager.log')
            >>> manager.update_alert_color('green')
        '''

        html = f'style=max-width: 40rem; background-color:{color}'
        set_action_update('alert-id', html)
        self.log(f'changed alert color: {color}')

    def update_menu(self, menu_state):
        '''
            Update whether the menu is active or not.

            >>> manager = BitcoinManager('blockchain_backup.bitcoin.manager.log')
            >>> manager.update_menu(constants.DISABLE_ITEM)
        '''

        html = f'state={menu_state}'
        set_action_update('nav-link', html)
        self.log(f'changed menu state: {menu_state}')

    def update_location(self, location):
        '''
            Send browser to a new location.

            >>> manager = BitcoinManager('blockchain_backup.bitcoin.manager.log')
            >>> manager.update_location(constants.BACKUP_URL)
        '''

        set_action_update(constants.LOCATION_NAME, location)
        self.log(f'changed location: {location}')
