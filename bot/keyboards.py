from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def schedule_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Every 6 hours", callback_data="schedule_6")],
        [InlineKeyboardButton("Every 12 hours", callback_data="schedule_12")],
        [InlineKeyboardButton("Daily (24h)", callback_data="schedule_24")],
        [InlineKeyboardButton("Turn off", callback_data="schedule_off")],
    ])


def clear_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Yes, clear everything", callback_data="confirm_clear"),
            InlineKeyboardButton("Cancel", callback_data="cancel_clear"),
        ]
    ])
