import csv
import logging
import requests
import zipfile
import io
import os
from config import settings

logger = logging.getLogger(__name__)

DHAN_SCRIP_MASTER_URL = "https://images.dhan.co/api-data/api-scrip-master.csv"
SCRIP_FILE = os.path.join(settings.BASE_DIR, "data", "api-scrip-master.csv")

class DhanHelper:
    def __init__(self):
        self.symbol_to_id = {}
        self.id_to_symbol = {}
        self._load_master()

    def _load_master(self):
        """Downloads and parses Dhan scrip master, caching it locally."""
        if not os.path.exists(SCRIP_FILE):
            logger.info("Downloading Dhan API Scrip Master...")
            try:
                resp = requests.get(DHAN_SCRIP_MASTER_URL, stream=True)
                resp.raise_for_status()
                with open(SCRIP_FILE, 'wb') as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                logger.info("Download complete.")
            except Exception as e:
                logger.error(f"Failed to download Dhan scrip master: {e}")
                return

        # Load Nifty 100 symbols
        try:
            from utils.nifty_100_symbols import NIFTY_100_SYMBOLS
            nifty_100_set = set(NIFTY_100_SYMBOLS)
        except ImportError:
            logger.error("Failed to load NIFTY_100_SYMBOLS. Falling back to an empty set.")
            nifty_100_set = set()

        logger.info("Parsing Dhan API Scrip Master for Nifty 100...")
        try:
            with open(SCRIP_FILE, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                count = 0
                for row in reader:
                    # Filter for NSE Equity
                    if row.get('SEM_EXM_EXCH_ID') == 'NSE' and row.get('SEM_SERIES') == 'EQ':
                        symbol = row.get('SEM_TRADING_SYMBOL')
                        if not symbol:
                            symbol = row.get('SM_SYMBOL_NAME')
                        # Filter by Nifty 100
                        if symbol and symbol.split('-')[0] in nifty_100_set:
                            sec_id = row.get('SEM_SMST_SECURITY_ID')
                            if sec_id:
                                self.symbol_to_id[symbol] = sec_id
                                self.id_to_symbol[sec_id] = symbol
                                count += 1
            logger.info(f"Loaded {count} Nifty 100 instruments from Dhan master.")
        except Exception as e:
            logger.error(f"Error parsing Dhan scrip master: {e}")

    def get_security_id(self, symbol: str) -> str:
        return self.symbol_to_id.get(symbol)

    def get_symbol(self, security_id: str) -> str:
        return self.id_to_symbol.get(security_id)

dhan_helper = DhanHelper()
