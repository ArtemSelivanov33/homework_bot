class ServerResponseError(Exception):
    """Исключение, которое возникает при неправильном ответе сервера."""
    def __init__(
        self, status_code, message="Сервер ответил некорректным кодом."
    ):
        self.status_code = status_code
        self.message = f'{message}: {status_code}'
        super().__init__(self.message)

class TelegramMessageError(Exception):
    """Исключение, при ошибке отправки сообщения в Telegram."""
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)
