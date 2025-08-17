

class BotStats:
    def __init__(self):
        self.deaths = 0
        self.gold_collected = 0
        self.diamonds_collected = 0

    def reset(self):
        self.deaths = 0
        self.gold_collected = 0
        self.diamonds_collected = 0