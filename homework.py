import logging
import os
import requests
import time

from dotenv import load_dotenv
from telebot import TeleBot

from exception import (
    ServerResponseError,
    TelegramMessageError
)

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACT_TOKEN')
TELEGRAM_TOKEN = os.getenv('TG_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TG_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверка доступности переменных окружения."""
    REQUIRED_VARIABLES = (
        PRACTICUM_TOKEN,
        TELEGRAM_TOKEN,
        TELEGRAM_CHAT_ID
    )

    for variables in REQUIRED_VARIABLES:
        if variables is None:
            return False
    return True


def send_message(bot, message):
    """Отправляет сообщение в Telegram-чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(f'Бот отправил сообщение "{message}"')
    except telebot.apihelper.ApiException as api_error:
        raise TelegramMessageError(
            f'Ошибка при отправке сообщения в Telegram: {api_error}'
        )


def get_api_answer(timestamp):
    """Делает запрос к API и возвращает ответ в формате Python."""
    request_kwargs = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': {'from_date': timestamp}
    }
    try:
        response = requests.get(**request_kwargs)
        #Не смог понять как убрать отсюда проверку,чтобы не делал,падают тесты.
        if response.status_code != 200:
            raise ServerResponseError(response.status_code)
        return response.json()
    except requests.exceptions.RequestException as e:
        raise ConnectionError(
            f'Ошибка API: {response.status_code}, {response.text},'
            f'Параметры запроса: {request_kwargs}'
        )


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API должен быть словарём.')
    if 'homeworks' not in response:
        raise KeyError('В ответе отсутствует ключ "homeworks".')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError('Значение ключа "homeworks" должно быть списком.')
    return homeworks


def parse_status(homework):
    """Извлекает статус проверки работы и формирует сообщение."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_name is None:
        raise KeyError('Отсутствует ключ "homework_name" в домашней работе.')
    if homework_status is None:
        raise KeyError('Отсутствует ключ "homework_status" в домашней работе.')
    if homework_status not in HOMEWORK_VERDICTS:
        raise ValueError(f'Неизвестный статус: {homework_status}')    
    return (f'Изменился статус проверки работы "{homework_name}". '
    f'{HOMEWORK_VERDICTS.get(homework_status)}')


def main():
    """Основная логика работы бота."""
    if check_tokens() == False:
        logging.critical(
            'Отсутствуют переменные окружения: *REQUIRED_VARIABLES'
        )
        message = 'Отсутствуют переменные окружения: *REQUIRED_VARIABLES'
        sys.exit(message)
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_message = None
    last_error_bot_message = None

    while True:
        try:
            response = get_api_answer(timestamp)
            logging.info('Начали запрос к API.')
            homeworks = check_response(response)
            current_timestamp = response.get('current_date', timestamp)
            if homeworks:
                for homework in homeworks:
                    homework_timestamp = int(
                        time.mktime(time.strptime(homework['date_updated'],
                        '%Y-%m-%dT%H:%M:%SZ'))
                    )
                    if homework_timestamp >= current_timestamp:
                        message = parse_status(homework)
                        logging.info('Начинаю проверку сообщения.')
                        if message != last_message:
                            try:
                                send_message(bot, message)
                                logging.info('Начинаю отправку сообщения.')
                                last_message = message
                            except (
                                telebot.apihelper.ApiException,
                                requests.RequestException
                            ) as err:
                                logging.error(
                                    f'Сбой API при выполнении HTTP-запроса:'
                                    f'{err}'
                                )
                                continue
                        else:
                            logging.debug(
                                'Сообщение совпадает с последним отправленным.'
                                'Пропускаем отправку.'
                            )
                    else:
                        logging.debug('Работа устарела. Пропускаем.')
            else:
                logging.debug("Отсутствие в ответе новых статусов")
        except requests.exceptions.RequestException as e:
            logging.error(
                f'Сетевая ошибка: {e},'
                f'Параметры запроса: {request_kwargs}'
            )
        except ServerResponseError as sr_error:
            logging.error(
                sr_error.message
            )
        except TelegramMessageError as api_error:
            logging.error(
                f'Ошибка при отправке сообщения в Telegram: {api_error}'
            )
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if message != last_error_bot_message:
                logging.error(message)
                send_message(bot, message)
                last_error_bot_message = message
        finally:
            timestamp = current_timestamp
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()

    logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
    )