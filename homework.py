import logging
import os
import requests
import time

from dotenv import load_dotenv
from telebot import TeleBot

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


logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)


def check_tokens():
    """Проверка доступности переменных окружения."""
    required_variables = [
        PRACTICUM_TOKEN,
        TELEGRAM_TOKEN,
        TELEGRAM_CHAT_ID
    ]
    missing_variable = [
        variable for variable in required_variables
        if os.getenv(variable) is None
    ]
    if missing_variable:
        logging.critical("Отсутствуют необходимые переменные окружения.")
        for variable in missing_variable:
            print(f"- {variable}")
        return False
    return True


def send_message(bot, message):
    """Отправляет сообщение в Telegram-чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(f'Бот отправил сообщение "{message}"')
    except Exception as err:
        logging.error(f'Сбой при отправке сообщения в Telegram: {err}')


def get_api_answer(timestamp):
    """Делает запрос к API и возвращает ответ в формате Python."""
    params = {'from_date': timestamp}
    try:
        response = requests.get(
            url=ENDPOINT,
            headers=HEADERS,
            params=params
        )
        if response.status_code != 200:
            logging.error(
                f'Ошибка API: {response.status_code}, {response.text}'
            )
            raise ConnectionError(f'Ошибка API: {response.status_code}')

        return response.json()

    except requests.exceptions.RequestException as e:
        logging.error(f'Сетевая ошибка: {e}')
        raise ConnectionError(f'Ошибка API: {response.status_code}')


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
    if homework_status not in HOMEWORK_VERDICTS:
        raise ValueError(f'Неизвестный статус: {homework_status}')
    verdict = HOMEWORK_VERDICTS.get(homework_status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if TELEGRAM_TOKEN is None:
        logging.critical(
            "Отсутствует переменная окружения: 'TELEGRAM_BOT_TOKEN'"
        )
        return
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if not homeworks:
                logging.debug("Отсутствие в ответе новых статусов")
                return
            for homework in homeworks:
                message = parse_status(homework)
                if message:
                    send_message(bot, message)
            timestamp = int(time.time())

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            send_message(bot, message)

        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
