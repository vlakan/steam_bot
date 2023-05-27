import time
import logging

from multiprocessing import Pool
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from fake_useragent import UserAgent
from data_base.postgresql_db import sql_add_item_command, sql_check_for_new_item, not_check_in, insert, \
    not_check_in_log, insert_log, delete, start_sql, clean_sql_states
from notifiers import get_notifier
from random import choice, randrange
from selenium.common.exceptions import NoSuchElementException
from config import TG_ID, API_TOKEN_BOT, EX_PATH, processes

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

file_handler = logging.FileHandler('app.log')
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
file_handler.setFormatter(file_formatter)

logger = logging.getLogger()
logger.addHandler(file_handler)

urls_list = []
with open('urls.txt') as file:
    lines = file.readlines()
    for line in lines:
        urls_list.append(line)
urls_list = [line.rstrip() for line in urls_list]

proxies_list = []
with open('proxies.txt', 'r') as file:
    lines = file.readlines()
    for line in lines:
        proxies_list.append(line.replace('\n', ''))
print(f'Кол-во proxy: {len(proxies_list)}')

data = []
with open('logins.txt') as file:
    lines = file.readlines()
    for line in lines:
        steam_login = line.split(':')[0]
        steam_password = line.split(':')[1]
        data.append({
            'steam_login': steam_login,
            'steam_password': steam_password
        })


def get_proxy(proxy_lists):
    while True:
        proxy = choice(proxy_lists)
        if not_check_in(value=proxy):
            insert(value=proxy)
            return proxy


def get_log_pass(proxy):
    data_list = data
    quantity_accounts = len(data_list)

    while True:
        rand_index = randrange(0, quantity_accounts)
        login = data_list[rand_index]['steam_login']
        password = data_list[rand_index]['steam_password']
        if not_check_in_log(value=login):
            insert_log(value=login, value2=proxy)
            return login, password


def get_chromedriver(proxy=None):
    user_agent = UserAgent()

    options = webdriver.ChromeOptions()

    options.add_argument(f'--proxy-server={proxy}')
    options.add_argument(f'--user-agent={user_agent}')
    options.add_argument("window-size=700,700")
    options.add_argument("disable-infobars")
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-blink-features=AutomationControlled')  # off webdriver mode
    options.add_experimental_option("excludeSwitches", ["enable-logging"])
    options.add_argument("--headless")

    s = Service(executable_path=EX_PATH)
    driver = webdriver.Chrome(service=s, options=options)

    return driver


def catch_req_error(driver):
    # requests
    try:
        driver.find_element(By.CLASS_NAME, 'error_ctn')
        return True
    except NoSuchElementException:
        return False


def catch_tryagain_error(driver):
    # try again
    try:
        driver.find_element(By.CLASS_NAME, 'newlogindialog_FailureTitle_A3Y-u')
        return True
    except NoSuchElementException:
        return False


def clean_errors(driver):
    if catch_req_error(driver):
        raise Exception('Try later')
    elif catch_tryagain_error(driver):
        raise Exception('Try again')


def authorization(driver, login, password):
    driver.get(url='https://steamcommunity.com/login/home/?goto=')
    time.sleep(randrange(10, 12))
    steam_login_input = driver.find_element(By.CSS_SELECTOR, "div[class='newlogindialog_TextField_2KXGK'] input["
                                                             "type='text']")
    steam_login_input.clear()
    steam_login_input.send_keys(login)
    driver.implicitly_wait(1)

    steam_password_input = driver.find_element(By.CSS_SELECTOR, "div[class='newlogindialog_TextField_2KXGK'] input["
                                                                "type='password']")
    steam_password_input.clear()
    steam_password_input.send_keys(password)
    steam_password_input.send_keys(Keys.ENTER)
    time.sleep(randrange(10, 14))


def sorting_and_notification(data_set, old_quantity=None, have=None):
    sql_add_item_command(data=data_set, have=have)
    telegram = get_notifier('telegram')
    if old_quantity:
        message = f'The number has changed!\n' \
                  f'{data_set[1]}\n\n{data_set[0]}\n{data_set[2]}$\n{old_quantity} -> {data_set[3]}\n{data_set[4]}\n'
    else:
        message = f'New skin!\n' \
                  f'{data_set[1]}\n\n{data_set[0]}\n{data_set[2]}$\n{data_set[3]}\n{data_set[4]}\n'

    telegram.notify(token=API_TOKEN_BOT, chat_id=TG_ID, message=message)


def get_data(url=None):
    proxy = get_proxy(proxies_list)
    login, password = get_log_pass(proxy)
    driver = get_chromedriver(proxy)

    try:
        time.sleep(randrange(2, 6))
        authorization(driver, login, password)

        # Errors
        clean_errors(driver)

        driver.get(url=url)
        time.sleep(randrange(11, 15))

        # Errors after url
        clean_errors(driver)

        logger.info(f'Authorization completed successfully! Login: {login} Proxy:{proxy}\n{url}')
        # Get all items
        while True:
            sticker_name = driver.find_element(By.XPATH, '//*[@id="findItemsSearchBox"]').get_attribute('value')
            if "'" in sticker_name:
                sticker_name = sticker_name.replace("'", "''")
            first_quantity = driver.find_element(By.CSS_SELECTOR, '#searchResultsRows').find_elements(By.TAG_NAME, 'a')

            for skin in first_quantity:
                skin_quantity = int(skin.find_element(By.CLASS_NAME, 'market_listing_num_listings_qty').text)
                if skin_quantity == 0:
                    continue
                skin_name = skin.find_element(By.CLASS_NAME, 'market_listing_item_name').text
                if "'" in skin_name:
                    skin_name = skin_name.replace("'", "''")
                skin_url = skin.get_attribute('href')
                skin_price = skin.find_element(By.CLASS_NAME, 'normal_price').text

                if ',' in skin_price:
                    skin_price = skin_price.replace(',', '')

                price = float((skin_price.split('$')[-1:])[0].split()[:-1][0])
                data_set = [skin_name, sticker_name, price, skin_quantity, skin_url]

                # Notifications
                checker = sql_check_for_new_item(name=skin_name, sticker=sticker_name)

                if checker:
                    old_quantity = int(checker[0])
                    if skin_quantity > old_quantity:
                        sorting_and_notification(data_set, old_quantity, have=True)
                else:
                    sorting_and_notification(data_set, have=False)

                data_set.clear()

            if driver.find_element(By.ID, 'searchResults_end').text == \
                    driver.find_element(By.ID, 'searchResults_total').text:
                break
            else:
                next_page = driver.find_element(By.ID, 'searchResults_btn_next')
                next_page.click()
                time.sleep(randrange(8, 12))

    except Exception as ex:
        logger.error(f'Error in main: {ex} Login: {login}, Proxy: {proxy}\n{url}')
    finally:
        delete(value=proxy)
        driver.close()
        driver.quit()


if __name__ == '__main__':
    clean_sql_states()
    start_sql()
    
    while True:
        try:
            with Pool(processes=processes) as pool:
                pool.map(get_data, urls_list)

        except Exception as ex:
            logger.error(f'Error in POOL: {ex}')
