
Blockchain Backup
-----------------


Blockchain Backup protects access to your Bitcoin Core wallet with automatic blockchain backups and makes restoring your blockchain if and when it gets damaged. Obviously there are many backup programs, but Blockchain Backup is specifically designed to ensure backups are done routinely and that everything necessary for a smooth restore is preserved.

Your Bitcoin Core wallet needs a local copy of the blockchain. It's very easy to damage your blockchain and therefore lose access to your wallet. Blockchain Backup makes it easy to recover quickly.

Blockchain Backup works with Bitcoin Core. You get your own non-custodial wallet. Your account balance isn't just a database entry at an exchange. You keep your money in your own hands. You have the keys.

You run Blockchain Backup instead of starting Bitcoin-QT or bitcoind directly. When you're not actively using your wallet, Blockchain Backup updates and backs up your blockchain. Whenever you need your wallet, Blockchain Backup pauses and opens your wallet for you via Bitcoin-QT. As soon as you're done you close Bitcoin-QT. Blockchain Backup then updates and protects your blockchain again. Remember that it's your responsibility to back up your wallet.

Blockchain Backup and Bitcoin Core run on your computer. You have the keys to <a href="https://cointelegraph.com/news/avoid-hosted-crypto-wallets-at-all-costs-warns-elon-musk">your own wallet.</a> For security, you can only access Blockchain Backup from your own machine. You get a local web server that lets you control everything from your local browser. Any attempt to remotely access Blockchain Backup is ignored.

Blockchain Backup runs in a virtual environment which is automatically created after the package is installed by the debian or red hat package manager.

You will manage Blockchain Backup via your browser on your local server by going to http://blockchain-backup.local. Configuration files are installed in /etc/nginx/sites-available and /etc/nginx/sites-enabled for easy management of Blockchain Backup.

Blockchain Backup never sends any of your data to any other computer or network.
