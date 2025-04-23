import re
def word_number_case(number, ifOne, ifTwo, ifFive, addNumber = False):
	result = ''
	num = number
	if number < 0:
		num = -number
	m = num % 10
	if m == 1:
		result = ifOne
	elif 2 <= m <= 4:
		result = ifTwo
	else:
		result = ifFive
	if 1 <= m <= 4:
		if 11 <= num % 100 <= 14:
			result = ifFive
	if addNumber:
		result = f"{number} {result}"
	return result

def word_number_case_days(number_of_days):
    return f"{word_number_case(int(number_of_days), 'день', 'дня', 'дней', addNumber=True)}"

def word_number_case_hours(number_of_days):
    return f"{word_number_case(int(number_of_days), 'час', 'часа', 'часов', addNumber=True)}"

def word_number_case_rubles(number_of_rubles):
    return f"{word_number_case(int(number_of_rubles), 'рубль', 'рубля', 'рублей', addNumber=True)}"

def word_number_case_tasks(number_of_tasks):
    return f"{word_number_case(int(number_of_tasks), 'заявка', 'заявки', 'заявок', addNumber=True)}"

def word_number_case_was(number):
    return f"{word_number_case(int(number), 'была', 'были', 'было', addNumber=False)}"

def word_number_case_sent(number):
    return f"{word_number_case(int(number), 'отправлена', 'отправлены', 'отправлено', addNumber=False)}"

class Partial(dict):
    def __missing__(self, key):
        # если ключ не найден — возвращаем сам плейсхолдер
        return '{' + key + '}'
    
def escape_markdown(text: str) -> str:
    """
    Экранирует все специальные символы Markdown, добавляя перед ними обратный слеш.
    Поддерживает CommonMark и MarkdownV2 (Telegram).
    """
    # Список всех спецсимволов Markdown / MarkdownV2
    # Для Telegram MarkdownV2: _ * [ ] ( ) ~ ` > # + - = | { } . !
    pattern = r'([\\`*_{}\[\]()#+\-.!|~>])'
    return re.sub(pattern, r'\\\1', text)

def safe_markdown_mention(actor) -> str:
    """
    Формирует кликабельную Markdown‑ссылку на пользователя без излишнего экранирования.
    Экранируем только [, ], ( ), и обратный слеш.
    """
    # Собираем имя
    raw = f"{actor.first_name}{(' ' + actor.last_name) if actor.last_name else ''}".strip() or str(actor.chat_id)
    # Экранируем только нужные символы
    escaped = re.sub(r'([\\\[\]\(\)])', r'\\\1', raw)
    return f"[{escaped}](tg://user?id={actor.chat_id})"

def get_mention(actor) -> str:
	if actor.username:
		mention = escape_markdown(f"@{actor.username}")
	else:
		mention = safe_markdown_mention(actor)
	return mention