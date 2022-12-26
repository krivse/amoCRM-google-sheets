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
    Токены и другие переменные автоматически обновляются и записаны в файл .env.
    !!! Файл myутм.env необходимо переименовать в .env
    Метод events_request() реализует сбор данных: events,
    аргументы на вход: filters, id_client, current_day
    По умолчанию выставлены аргументы

    В первый запрос необходимо передать текущий день для аргумента current_day
    C его помощью будет происходить запись в ячейку google_shits каждый новый день
    При создании новой формы или обновлении текущей - нужно снова передать current_day
    Значение сохраняется в файл .env из которого происходит перерасчёт дней.

    Передача аргументов для выборки:
        None or '' = получение всех ['events']
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
        self.filters = ''
        self.param_id = '/'
        self._connected()

    def _connected(self):
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
        if self._time_now - float(os.getenv('LIFETIME_TOKEN')) <= int(os.getenv('EXPIRES_IN')):
            self._update_tokens()
        else:
            return

    def _get_tokens(self, response):
        self._lifetime_token = dotenv.set_key(dotenv_path, 'LIFETIME_TOKEN', str(time.time()))
        self._code = dotenv.set_key(dotenv_path, 'CODE', self._code)
        self._access_token = dotenv.set_key(dotenv_path, 'ACCESS_TOKEN', response['access_token'])
        self._refresh_token = dotenv.set_key(dotenv_path, 'REFRESH_TOKEN', response['refresh_token'])
        self._expires_in = dotenv.set_key(dotenv_path, 'EXPIRES_IN', str(response['expires_in']))
        return

    def _update_tokens(self):
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
        if self._access_token is None:
            token = os.getenv("ACCESS_TOKEN")
        else:
            token = self._access_token[2]
        params = {'Authorization': f'Bearer {token}'}
        if param_id != '':
            response = requests.get(f'https://ivanskywalker.amocrm.ru/api/v4/events/{param_id}', headers=params)  # ?filter[created_at][from]={1671898064}&filter[created_at][to]={1671912877}
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
        if os.getenv("RECORDING_PERIOD") == '' or not current_day is None:
            dotenv.set_key(dotenv_path, 'RECORDING_PERIOD', str(current_day))
            return current_day - date.fromtimestamp(event_day).day
        else:
            return int(os.getenv("RECORDING_PERIOD")) - date.fromtimestamp(event_day).day + 2


if __name__ == "__main__":
    app = ManagerAmoCRM(
        '4ded840c-b376-4608-980c-3bdfe48da4a3',
        'VmY27yuuXfTwufoqFSZFNkS1hHfm7TpsT1E5THa7ZtJRvZMSVbj9AatKxeI5KrqT',
        'ivanskywalker',
        'def50200d9544c4949d68bbd7ee9c7471ed77f01b9b10639673de1f82e58b1a017db3e24316912fe0ea91c0cffd501ac54012b462b593d46d862485ec28b38337adbb4b829cd03b08704177dea7659485a0b5f0033b9e9a2b55030b5114233ea9fb799a53041fc3187803bad5f5cac5defea3141bbcfcaac1b05d2e50d9cd39e120de8529bcd060d30deebe096e439d24f4108ba1c8d0b2bd46f065092769b60f2496c455243e56b3f4566456cccf584f9a3596d9d5e39c2e14d8b1da9dab25b81664b94ec9a9ca60d0fdd26d4fa43c232a285446c66ca1e051227a0e293a7830806f131f4b2e9b5c30201a94d7d18d21382799f3a5aaafad1d2fe0f9ff730cb122c4f45ac7df53ecdcabd9630b4e7a802922682a81937ce8aaa72fdc12b8e90dd7ad88cbf478aeab0ce423d47edc98b3f8131da540724d31e12c4cb46f9d437ffb5317f99796b82d50ccaf7cb30298020392776fb40c9e864b1fcd8915e8474f6425cb3f07a84e79e9601651e1feb48fe4098a88e54328116527a9f5927ded9056bd0177d21a3d68ef0338cb6a7946d2974ea89cbbd664a2e8ea6e5cc501d350eac0a274b3fa9f5938a273fe4f692a56beeffcbb3d3c2fa71af6c4059145158dd8fe5b996c3daede370a94af111bdd6a1',
        'https://test.com'
        )
    app.events_request()  # None or ''=get['events'], param_id=str(id), filters=str(filters, page, limit), day=день с какого начинается отчёт, передаётся один, если запроос меняется, то пердаётся заного


