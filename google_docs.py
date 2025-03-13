import asyncio
import string

from google.oauth2 import service_account
from googleapiclient.discovery import build

from db import get_module_dates_from_db, get_modules_from_db

SERVICE_ACCOUNT_FILE = "credentials.json"

SPREADSHEET_ID = "1N5bwUUy-vnAAGTv2bh_JnFsyYHLbZ-1bNTpxvgxDcHw"

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']


def get_sheets_service():
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    return build('sheets', 'v4', credentials=credentials)

async def get_column_letter(index):
    """Преобразует индекс в буквенное представление (A-Z, AA, AB...)"""
    result = ""
    while index >= 0:
        result = string.ascii_uppercase[index % 26] + result
        index = index // 26 - 1
    return result

async def merge_cells(start_row, end_row, start_column, end_column):
    service = get_sheets_service()

    requests = [
        {
            "mergeCells": {
                "range": {
                    "sheetId": 1764031813,  # Номер листа (можно получить через API, если нужно)
                    "startRowIndex": start_row,  # Стартовый индекс строки
                    "endRowIndex": end_row,  # Конечный индекс строки
                    "startColumnIndex": start_column,  # Стартовый индекс колонки (E = 4)
                    "endColumnIndex": end_column  # Конечный индекс колонки (F = 6)
                },
                "mergeType": "MERGE_ALL"  # Тип объединения (MERGE_ALL для полного объединения)
            }
        }
    ]

    try:
        body = {'requests': requests}
        service.spreadsheets().batchUpdate(
            spreadsheetId=SPREADSHEET_ID, body=body).execute()
    except Exception as e:
        await merge_cells(start_row, end_row, start_column, end_column + 1)


async def unmerge_cells(start_row, end_row, start_column, end_column):
    service = get_sheets_service()

    requests = [
        {
            "unmergeCells": {
                "range": {
                    "sheetId": 1764031813,  # Номер листа (можно получить через API, если нужно)
                    "startRowIndex": start_row,  # Стартовый индекс строки
                    "endRowIndex": end_row,  # Конечный индекс строки
                    "startColumnIndex": start_column,  # Стартовый индекс колонки (E = 4)
                    "endColumnIndex": end_column  # Конечный индекс колонки (F = 6)
                }
            }
        }
    ]

    try:
        body = {'requests': requests}
        service.spreadsheets().batchUpdate(
            spreadsheetId=SPREADSHEET_ID, body=body).execute()
    except Exception as e:
        await unmerge_cells(start_row, end_row, start_column, end_column + 1)

async def auto_merger(s, e, sc, ec):
    await merge_cells(s, e, sc, ec)
    await unmerge_cells(s, e, sc, ec)
    await merge_cells(s, e, sc, ec)

async def add_new_column(index):
    service = get_sheets_service()

    # Определяем параметры вставки нового столбца
    requests = [
        {
            "insertDimension": {
                "range": {
                    "sheetId": 1764031813,  # ID листа (можно получить через API)
                    "dimension": "COLUMNS",  # Вставляем новый столбец
                    "startIndex": index,  # Индекс столбца, перед которым будет вставлен новый (например, вставляем перед 4-м)
                    "endIndex": index+1  # Указываем конец диапазона
                },
                "inheritFromBefore": True  # Наследовать форматирование от предыдущего столбца
            }
        }
    ]

    # Отправляем запрос на обновление таблицы
    try:
        body = {'requests': requests}
        service.spreadsheets().batchUpdate(
            spreadsheetId=SPREADSHEET_ID, body=body
        ).execute()
    except Exception as e:
        pass

async def delete_column(time):
    service = get_sheets_service()

    sheet = service.spreadsheets().values()
    result = sheet.get(spreadsheetId=SPREADSHEET_ID, range="Отметки!A:Z").execute()
    values = result.get("values", [])

    column_index = None
    for row_index, row in enumerate(values[1]):
        if row == time:
            column_index = row_index

    title = None
    title_letter = None
    if values[0][column_index] != '':
        title = values[0][column_index]
        title_letter = get_column_letter(column_index)

    requests = [
        {
            "deleteDimension": {
                "range": {
                    "sheetId": 1764031813,
                    "dimension": "COLUMNS",
                    "startIndex": column_index,
                    "endIndex": column_index + 1
                }
            }
        }
    ]

    body = {"requests": requests}

    try:
        service.spreadsheets().batchUpdate(
            spreadsheetId=SPREADSHEET_ID,
            body=body
        ).execute()

        if title and title_letter:
            update_range = f"Отметки!{title_letter}1"

            body = {
                'values': [[title]]
            }

            service.spreadsheets().values().update(
                spreadsheetId=SPREADSHEET_ID,
                range=update_range,
                valueInputOption="RAW",
                body=body
            ).execute()
    except Exception as e:
        pass


def update_in_google_sheet(data, range_to_update):
    service = get_sheets_service()

    table_name, table_letter = range_to_update.split('!')

    sheet = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range="B2:B"
    ).execute()

    values_old = sheet.get("values", [])

    table_num = 0

    if table_letter == "B":
        for i in range(len(values_old)):
            if str(values_old[i][0]) == str(data[0]):
                range_to_update = f"{table_name}!B{i+2}"
                table_num = i+2
                break
        else:
            range_to_update = f"{table_name}!B{len(values_old) + 2}"
            table_num = len(values_old) + 2

    values = []
    for user in data:
        values.append([str(user)])

    body = {
        'values': values
    }

    service.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=range_to_update,
        valueInputOption="RAW",
        body=body
    ).execute()

    return table_num

def find_and_update_in_google_sheet(user_id, answer, date_to_find, range_to_update):
    service = get_sheets_service()

    sheet = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=range_to_update
    ).execute()

    values = sheet.get("values", [])

    row_index = 2
    for i, row in enumerate(values):
        if row[0] == str(user_id):
            row_index = i + 1
            break

    column_index = None
    for i, row in enumerate(values[1]):
        if row == date_to_find:
            column_index = i
            break

    if row_index is None or column_index is None:
        return False

    column_letter = get_column_letter(column_index)

    update_range = f"Отметки!{column_letter}{row_index}"

    body = {
        "values": [[answer]]
    }

    service.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=update_range,
        valueInputOption="RAW",
        body=body
    ).execute()

async def cmd_user_google_sheet(data: list, range_to_update: str):
    range_to_update = "Пользователи!" + range_to_update
    return await asyncio.to_thread(update_in_google_sheet, data, range_to_update)

async def cmd_reminders_google_sheet(user_id: list, answer: str, date, range_to_update: str):
    range_to_update = "Отметки!" + range_to_update
    await asyncio.to_thread(find_and_update_in_google_sheet, user_id, answer, date, range_to_update)


async def get_existing_dates_in_sheet(module_name, len_date):
    """Получаем уже существующие даты для модуля в Google Sheets."""
    service = get_sheets_service()

    sheet = service.spreadsheets().values()
    result = sheet.get(spreadsheetId=SPREADSHEET_ID, range="Отметки!A:Z").execute()
    values = result.get("values", [])
    # Ищем строки модуля и извлекаем даты
    existing_dates = []
    modules = await get_modules_from_db()
    for row_index, row in enumerate(values[0]):
        if row == modules[module_name][0]:
            for date_row in values[1][row_index: row_index + len_date]:
                if date_row:
                    existing_dates.append(date_row)
                else:
                    break
    return existing_dates


async def add_missing_dates_to_sheet(module_name, new_dates, len_existing_dates, update_index):
    """Добавляем отсутствующие даты в Google Sheets для указанного модуля."""
    service = get_sheets_service()

    sheet = service.spreadsheets().values()
    result = sheet.get(spreadsheetId=SPREADSHEET_ID, range="Отметки!A:AZ").execute()
    values = result.get("values", [])

    insert_index = None
    modules = await get_modules_from_db()
    for row_index, row in enumerate(values[0]):
        if row == modules[module_name][0]:
            insert_index = row_index
            break

    if len_existing_dates > 0:
        for i in range(len(update_index)):
            if not len(values[1]) == (insert_index + len_existing_dates + i) + 1:
                await add_new_column(insert_index + len_existing_dates + i)
                await asyncio.sleep(5)

    if insert_index is None:
        if values[1]:
            insert_index = len(values[1])
        else:
            insert_index = 1

        values[0].append(modules[module_name][0])

        body = {"values": [[modules[module_name][0]]]}

        update_range = f"Отметки!{get_column_letter(insert_index)}1"

        service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=update_range,
            valueInputOption="RAW",
            body=body
        ).execute()

    column_letter = get_column_letter(insert_index)
    column_letter_last = get_column_letter(insert_index + len(new_dates) - 1)

    await auto_merger(0, 1, insert_index, insert_index + len(new_dates))

    if len_existing_dates < 0:
        update_range = f"Отметки!{column_letter}{2}:{column_letter_last}2"

        body = {"values": [new_dates]}

        service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=update_range,
            valueInputOption="RAW",
            body=body
        ).execute()
    else:
        update_range = f"Отметки!{column_letter_last}2"

        body = {"values": [update_index]}

        service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=update_range,
            valueInputOption="RAW",
            body=body
        ).execute()


async def sync_module_dates():
    """Синхронизируем даты занятий модуля между SQLite и Google Sheets."""
    while True:
        for module_name in await get_modules_from_db():
            db_dates = await get_module_dates_from_db(module_name)
            sheet_dates = await get_existing_dates_in_sheet(module_name, len(db_dates))

            new_dates = [date for date in db_dates if date not in sheet_dates]

            if new_dates:
                await add_missing_dates_to_sheet(module_name,
                                                 db_dates, len(sheet_dates) - len(new_dates), new_dates)

        await asyncio.sleep(60 * 30)
