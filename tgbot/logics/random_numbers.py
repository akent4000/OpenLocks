import random
from tgbot.logics.constants import Constants

class RandomNumberList:
    def __init__(self, num_length: int, seed: int):
        self.n = num_length
        self.max_value = 10**num_length - 1
        self.numbers = list(range(1, self.max_value + 1))
        random.seed(seed)
        random.shuffle(self.numbers)

    def get(self, i: int) -> int:
        index = i % self.max_value
        return self.numbers[index]
    
random_number_list = RandomNumberList(Constants.NUMBER_LENGTH, Constants.RANDOM_LIST_SEED)