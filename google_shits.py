import gspread


def update_sheets(number, events):
    """
    При подключении необходимо получить ключ service-account на google-sheets
    Указать в gp.open('...') - какая таблицу открывается
    :param number: передаётся номер строки, например, "A1"
    :param events: json объект
    """
    gp = gspread.service_account(filename='project-integration-amocrm.json')
    gsheet = gp.open('amoCRM')
    wsheet = gsheet.worksheet("Лист1")
    wsheet.update_acell(f'A{number}', str(events))

