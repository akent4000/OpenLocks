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