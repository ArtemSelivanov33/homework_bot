import logging
import os
import requests
import sys
import time

from dotenv import load_dotenv
from telebot import TeleBot
from telebot.apihelper import ApiException

from exception import (
    ServerResponseError,
    TelegramMessageError
)

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

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
    REQUIRED_VARIABLES = [
        ('Токен ЯПрактикум', PRACTICUM_TOKEN),
        ('Токен Телеграмм', TELEGRAM_TOKEN),
        ('Телеграмм CHAT_ID', TELEGRAM_CHAT_ID),
    ]
    missing_variables = [
        f"{name}: {value}" for name, value in REQUIRED_VARIABLES
        if value is None
    ]
    if missing_variables:
        logging.critical(
            "Отсутствуют необходимые переменные окружения: %s",
            ', '.join(missing_variables)
        )
        return False
    return True


def send_message(bot, message):
    """Отправляет сообщение в Telegram-чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(f'Бот отправил сообщение "{message}"')
    except ApiException as api_error:
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
    except requests.exceptions.RequestException as e:
        raise ConnectionError(
            f'Ошибка API: {e},'
            f'Параметры запроса: {request_kwargs}'
        )
    if response.status_code != 200:
        raise ServerResponseError(response.status_code)
    return response.json()


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
    return (
        f'Изменился статус проверки работы "{homework_name}".'
        f'{HOMEWORK_VERDICTS.get(homework_status)}'
    )


def process_homeworks(homeworks, current_timestamp, bot, last_message):
    """Обрабатывает домашние задания и отправляет сообщения."""
    homework = homeworks[0]
    homework_timestamp = int(
        time.mktime(
            time.strptime(homework['date_updated'], '%Y-%m-%dT%H:%M:%SZ')
        )
    )
    if homework_timestamp >= current_timestamp:
        message = parse_status(homework)
        if message != last_message:
            send_message(bot, message)
            last_message = message
            logging.info('Сообщение отправлено: %s', message)
        else:
            logging.debug(
                'Сообщение совпадает с последним отправленным.'
                'Пропускаем отправку.'
            )
    else:
        logging.debug('Работа устарела. Пропускаем.')
    return last_message


def send_except_error(error, bot, last_error_message):
    """Отправляет последнее сообщение об ошибке, исключая дублирование."""
    logging.error(f'Сбой в работе программы: {error}')
    message = f'Сбой в работе программы: {error}'
    if message != last_error_message:
        logging.error(message)
        send_message(bot, message)
        last_error_message = message
    return last_error_message


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        sys.exit()
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_message = None
    last_error_message = None

    while True:
        try:
            logging.info('Начали запрос к API.')
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            current_timestamp = response.get('current_date', timestamp)
            if homeworks:
                last_message = process_homeworks(
                    homeworks,
                    current_timestamp,
                    bot,
                    last_message
                )
                current_timestamp = response.get('current_date', timestamp)
            else:
                logging.debug("Отсутствие в ответе новых статусов")
        except TelegramMessageError as api_error:
            logging.error(
                f'Ошибка при отправке сообщения в Telegram: {api_error}'
            )
        except Exception as error:
            last_error_message = send_except_error(
                error,
                bot,
                last_error_message
            )
        finally:
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
