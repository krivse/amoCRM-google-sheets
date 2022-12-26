import requests
import os
from dotenv import load_dotenv
from os.path import join, dirname
import dotenv
import time
from datetime import date

from google_shits import update_sheets

dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)


class ManagerAmoCRM:
    """
    Класс реализует подключение к amoCRM с помощью протокола Oauth2.
    Нужно на вход передать необходимые ключи для подключения.
    Токены и другие переменные автоматически обновляются и записаны в файл .env.
    !!! Файл myenv.env необходимо переименовать в .env
    Метод events_request() реализует сбор данных: events,
    аргументы на вход: filters, id_client, current_day
    По умолчанию установлены значения.
    В первый запрос необходимо передать текущий день для аргумента current_day
    C его помощью будет происходить запись в ячейку google_shits каждый новый день
    При создании новой формы или обновлении текущей - нужно снова передать current_day
    Значение сохраняется в файл .env из которого происходит перерасчёт дней.
    Передача аргументов для выборки:
        '' = получение всех ['events']
        param_id=str(id) - необязательный аргумент, который по умолчанию ''
        filters=str(filters, page, limit) - необязательный аргумент, который по умолчанию ''
    """
    def __init__(self, client_id, client_secret, subdomain, code, uri):
        self._client_id = client_id
        self._client_secret = client_secret
        self._subdomain = subdomain
        self._redirect_uri = uri
        self._code = code
        self._access_token = None
        self._refresh_token = None
        self._lifetime_token = None
        self._time_now = time.time()
        self._expires_in = None
        self._connected()

    def _connected(self):
        """
        Первичное подключение к amoCRM и получение токена и записывается .env,
        откуда в дальнейшем будет вызываться.
        Если подключение было произведено ранее, то выполняется get_запрос
        Если access токен истёк - получаем новый и перезаписываем в .env
        """
        if self._code != os.getenv('CODE') or os.getenv('CODE') == '':
            data = {
                "grant_type": "authorization_code",
                "code": self._code,
                "redirect_uri": self._redirect_uri,
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            }
            try:
                response = requests.post(f"https://{self._subdomain}.amocrm.ru/oauth2/access_token", json=data)
            except requests.exceptions.RequestException as err:
                raise err
            else:
                if response.status_code != 200:
                    raise Exception(response.json()['hint'])
                response = response.json()
                self._get_tokens(response)
        elif self._time_now - float(os.getenv('LIFETIME_TOKEN')) >= int(os.getenv('EXPIRES_IN')):
            self._update_tokens()
        else:
            return

    def _get_tokens(self, response):
        """Записываем необходимые данные о токене в .env"""
        self._lifetime_token = dotenv.set_key(dotenv_path, 'LIFETIME_TOKEN', str(time.time()))
        self._code = dotenv.set_key(dotenv_path, 'CODE', self._code)
        self._access_token = dotenv.set_key(dotenv_path, 'ACCESS_TOKEN', response['access_token'])
        self._refresh_token = dotenv.set_key(dotenv_path, 'REFRESH_TOKEN', response['refresh_token'])
        self._expires_in = dotenv.set_key(dotenv_path, 'EXPIRES_IN', str(response['expires_in']))
        return

    def _update_tokens(self):
        """Обновление токенов с последующей их записью в .env."""
        body = {
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "grant_type": "refresh_token",
            "refresh_token": os.getenv('REFRESH_TOKEN'),
            "redirect_uri": self._redirect_uri
        }
        response = requests.post(f'https://{self._subdomain}.amocrm.ru/oauth2/access_token', json=body)
        if response.status_code == 200:
            response = response.json()
            self._access_token = dotenv.set_key(dotenv_path, 'ACCESS_TOKEN', response['access_token'])
            self._refresh_token = dotenv.set_key(dotenv_path, 'REFRESH_TOKEN', response['refresh_token'])
            return
        raise EnvironmentError(f'Cant refresh token {response.json()}')

    def events_request(self, filters='', param_id='', current_day=None):
        """
        :param '' : get запрос на выборку всех данных ['events']
        :param filters: str(filters, page, limit)
        :param param_id: str(id)
        :param current_day: Рассчёт прошедших дней
        """
        if self._access_token is None:
            token = os.getenv("ACCESS_TOKEN")
        else:
            token = self._access_token[2]
        params = {'Authorization': f'Bearer {token}'}
        if param_id != '':
            response = requests.get(f'https://ivanskywalker.amocrm.ru/api/v4/events/{param_id}', headers=params)
            events = response.json()
            created_at = events['created_at']
            value = self._next_day(created_at, current_day)
            update_sheets(value, events)
        else:
            response = requests.get(f'https://ivanskywalker.amocrm.ru/api/v4/events{filters}', headers=params)
            events = response.json()
            created_at = events['_embedded']['events'][0]['created_at']
            value = self._next_day(created_at, current_day)
            update_sheets(value, events)

    @staticmethod
    def _next_day(event_day, current_day):
        """Функция рассчёта дней для google-sheets."""
        if os.getenv("RECORDING_PERIOD") == '' or current_day is not None:
            dotenv.set_key(dotenv_path, 'RECORDING_PERIOD', str(current_day))
            return current_day - date.fromtimestamp(event_day).day
        else:
            return int(os.getenv("RECORDING_PERIOD")) - date.fromtimestamp(event_day).day + 1


if __name__ == "__main__":
    app = ManagerAmoCRM(
        'a7bdd0ee-9e88-4c02-aef5-3858c2c1a72a',
        'MO10joBN5Ennvn1bykSo3joFPxgX6D1wJOkkNPvrMHj6nVOzprdYOkwmiyBPsFeg',
        'ivanskywalker',
        'def50200173e02773a65adf6e8df2bbec5e0a0b98f17e08692b11d6a2c3787de6a202d7a09a811bdfbd667666dd7e991d3786958ce8ec914a655ca7e811cc4d10fadebaf3b7db6fa1c558e803e13c46427c4d69689ee184a7fe6ef45b5d795bd29200d3c5b19719baa4a39955ec17b22b07867248cab82719d4ece82e72ddf9b0cf7bf49fb086f44109ed1e5104790ac9aa944168d080177e2fcd32874ab2ba251ad0a29a749b1db0fe3247ca9c30cd91aa2537f5b5be3813a979696800c8a982dbb454475b748ee8632a961b373a22e2dd7d99a8d0934d7801b80c27094824c1b94c8840a80e2ecd14e10598263228d944e20b496c8e363655882956a2919a9dbd77974b0620d878278c5e99ba790a9e2648a5e62371f458f7eda9beaf76c44f57709cee6837e8dfe2c8ac8438f90fe1d1ddee21f7a8e9152c306aab09293e40d1dbb7550cf30d17262ba9b2b98009243e270094c3f91aefa55517d28a248d67432e70c5396c72c7be529fed4d8f1737be441c8f18eea36786c4dd569c569cee09084bcbf66dcb4b0724f18fecb2f161c3cd120c5d020873bfa0c42fc84aee29c51fd8cc781e9656a39001040005f11578a882f6b9479ceaa9cc6abb9df840396fb908398c494292e2f2a3f628c90ff34',
        'https://test.com'
        )
    app.events_request()
