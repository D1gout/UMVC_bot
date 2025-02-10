import asyncio
from google.oauth2 import service_account
from googleapiclient.discovery import build

SERVICE_ACCOUNT_FILE = "credentials.json"

SPREADSHEET_ID = "1N5bwUUy-vnAAGTv2bh_JnFsyYHLbZ-1bNTpxvgxDcHw"

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']


def get_sheets_service():
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    return build('sheets', 'v4', credentials=credentials)


def update_in_google_sheet(data, range_to_update):
    service = get_sheets_service()

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

async def cmd_user_google_sheet(data: list, range_to_update: str):
    range_to_update = "Пользователи!" + range_to_update
    await asyncio.to_thread(update_in_google_sheet, data, range_to_update)
