"""Run this script with |python run.py|."""

import imp
import os

import bot
honbot = imp.load_source('honbot', './honbot')

def load_config():
  '''Copied from main() in pyHoNBot/honbot.'''
  config_modules = []
  for config_name in honbot.config_names('trivia_bot'):
    name = os.path.basename(config_name).split('.')[0] + '_config'
    print config_name
    module = imp.load_source(name, config_name)
    module.filename = config_name

    if not hasattr(module, 'prefix'):
       module.prefix = r'\.'

    config_modules.append(module)
  return config_modules


def main():
  # Create the pyHoNBot and log in.
  configs = load_config()
  config = configs[0]

  if config:
    # Create the trivia bot.
    trivia_bot = bot.Bot(config)

    # Run the pyHoNBot.
    trivia_bot.run()


if __name__ == '__main__':
  main()