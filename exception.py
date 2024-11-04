class ServerResponseError(Exception):
    """Исключение, которое возникает при неправильном ответе сервера."""


class TelegramMessageError(Exception):
    """Исключение, при ошибке отправки сообщения в Telegram."""
