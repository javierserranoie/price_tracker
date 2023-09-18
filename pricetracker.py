#!/usr/bin/env python
# coding: utf-8

# In[ ]:

import requests
from lxml import html
import backoff
from datetime import datetime
import pandas as pd
import telegram
from tabulate import tabulate
from typing import List
import numpy as np
import asyncio
import logging
from logdecorator import log_on_start, log_on_error
from decouple import config

logging.basicConfig(level=logging.DEBUG)  # Set your desired log level

logger = logging.getLogger(__name__)


# In[ ]:

PARQUET_PATH = f"{config('LOCATION')}/pc_prices.parquet"
    
NOW = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0"
}

AMZ_XPATHS = ['//*[@id="corePriceDisplay_desktop_feature_div"]/div[1]/span[3]/span[2]/span[1]', 
              '//*[@id="corePriceDisplay_desktop_feature_div"]/div[1]/span[2]/span[2]/span[1]',
              '/html/body/div[2]/div/div[8]/div[4]/div[4]/div[12]/div/div[1]/div[3]/div[1]/span[3]/span[2]/span[1]']


COM_XPATHS = ['//*[@id="actualprice"]']


class PriceNotFoundException(Exception):
    pass


@log_on_start(logging.DEBUG, "Start downloading {url:s}...")
@log_on_error(logging.ERROR, "Error on downloading {url:s}: {e!r}",
              on_exceptions=IOError,
              reraise=True)
def get_url_content(url: str) -> str:
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    return response.text


@log_on_start(logging.DEBUG, "Extract price")
@log_on_error(logging.ERROR, "Error to parse {text:s} on {e!r}",
              on_exceptions=Exception,
              reraise=True)
def extract_price_from_html(text: str, element_xpaths: List[str]) -> str:
    # Parse the HTML content using lxml
    tree = html.fromstring(text)

    # Use XPath to extract text from the specified element
    for element_xpath in element_xpaths:
        try:
            return tree.xpath(element_xpath)[0].text
        except IndexError:
            pass
    raise PriceNotFoundException(f"price not found")


@backoff.on_exception(backoff.expo, 
                      PriceNotFoundException, 
                      max_tries=5,
                      jitter=None
                      )
def get_prices(tracker: dict, element_xpaths: List[str], round: int = 1, provider: str= None) -> dict:
    ans = {
        "provider": provider,
        "date": NOW
    }
    for id, url in tracker.items():
        if url is None:
            ans[id] = np.nan
        else:
            try:
                text = get_url_content(url)
                price = extract_price_from_html(text, element_xpaths)
                ans[id] = float(price.replace(',', '.')) + round
            except:
                raise PriceNotFoundException(f"price not found for {url}")
    return ans


def get_delta_dataset(*prices, keys=None):
    _df = pd.concat([pd.DataFrame([p]) for p in prices]).reset_index(drop=True)
    _df["total"] = np.round(_df.min()[keys].sum(), decimals=2)
    return _df


def append_to_parquet_prices(parquet_path, new_dataset):
    prev_df = pd.read_parquet(parquet_path)
    new_dataset["build"] = (prev_df.build.max() or 0) + 1
    df = pd.concat([prev_df, new_dataset]).drop_duplicates(["provider", "date"]).reset_index(drop=True)
    df.to_parquet(parquet_path)
    return df


def process_dataset(df):
    columns = ['Caja', 'CPU', 'Motherboard', 'GPU', 'HDD', 'RAM']
    df['date'] = pd.to_datetime(df['date'])
    last_date_df = df[df['date'] == df['date'].max()]
    result_df = pd.DataFrame({'Minimum Values': last_date_df[columns].min(), 'Provider': ''})
    for column in columns:
        result_df.at[column, 'Provider'] = last_date_df.loc[last_date_df[column].idxmin(), 'provider']
    result_df.loc["total", :] = last_date_df[["total"]].min().total
    return tabulate(result_df, headers='keys', tablefmt='fancy_grid')


def get_telegram_config():
    token = config("TELEGRAM_TOKEN")
    chat_id = config("TELEGRAM_CHAT_ID")
    
    if not token:
        raise Exception("TELEGRAM_TOKEN not found")  

    if not chat_id:
        raise Exception("TELEGRAM_CHAT_ID not found")
    
    return token, chat_id


async def asend_message(html_message):
    token, chat_id = get_telegram_config()
    _html = telegram.constants.ParseMode.HTML
    bot = telegram.Bot(token)
    await bot.send_message(chat_id=chat_id, disable_notification=True, parse_mode=_html, text=html_message)


def send_message(message):
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(asend_message(message))
    finally:
        loop.close()

# In[ ]:

if __name__ == "__main__":
    try:
        amazon_tracker = {
            "Caja": "https://www.amazon.es/dp/B09VMBJJ7L",
            "CPU": "https://www.amazon.es/dp/B09MDFH5HY",
            "Motherboard": "https://www.amazon.es/dp/B0BNQFXLJR",
            "GPU": "https://www.amazon.es/dp/B08Y91QVG8",
            "HDD": "https://www.amazon.es/Crucial-Plus-500GB-PCIe-5000MB/dp/B0B25NTRGD?crid=ASF82VWUNQRK&keywords=Crucial%2BP3%2BPlus%2B500gb&qid=1689043943&sprefix=crucial%2Bp3%2Bplus%2B500g%2Caps%2C90&sr=8-1&linkCode=sl1&tag=refresh0e-20&linkId=2e3eba584e88fe99a5928e1585850f5f&language=en_US&ref_=as_li_ss_tl&th=1",
            "RAM": 'https://www.amazon.es/Corsair-Vengeance-3200MHz-Desktop-Memory/dp/B0143UM4TC?crid=2FSIH8KL6OF09&keywords=Corsair%2BDDR4-3200&qid=1689043915&sprefix=corsair%2Bddr4-3200%2Caps%2C93&sr=8-1&linkCode=sl1&tag=refresh0e-20&linkId=ff5579ff11d308faa798f52bea670d83&language=en_US&ref_=as_li_ss_tl&th=1',
        }
        amazon_prices = get_prices(amazon_tracker, AMZ_XPATHS, provider="AMZ")

        coolmod_tracker = {
            "Caja": None,
            "CPU": "https://www.coolmod.com/intel-core-i5-12400f-4-4ghz-socket-1700-boxed-procesador/",
            "Motherboard": "https://www.coolmod.com/asus-rog-strix-b760-i-gaming-wifi-socket-1700/",
            "GPU": "https://www.coolmod.com/powercolor-fighter-amd-radeon-rx-6700-xt-12gb-gddr6-tarjeta-grafica/",
            "HDD": "https://www.coolmod.com/crucial-p5-plus-500gb-pcie-nvme-disco-duro-m-2/",
            "RAM": 'https://www.coolmod.com/corsair-vengeance-lpx-negro-16gb-2x8gb-3200-mhz-pc4-25600-cl16-memoria-ddr4/',
        }
        coolmod_prices = get_prices(coolmod_tracker, COM_XPATHS, round=0, provider="COM")

        new_df = get_delta_dataset(
            amazon_prices,
            coolmod_prices,
            keys=coolmod_tracker.keys()
        )
        # df = append_to_parquet_prices(get_delta_dataset, new_df)
        
        _now = datetime.strptime(NOW, "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d")
        message = f"[{_now}] latest total is: {new_df[['total']].min().total}\n\n<pre>{process_dataset(new_df)}</pre>"
    except Exception as e:
        message = f"Something went wrong!!\n{e}"

    send_message(message)
