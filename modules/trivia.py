#!/usr/bin/env python
"""
Start by configuring the configuration file for your bot. You need to make sure
the person/people starting the bot are listed as Owners. You also need to give
the bot a list of channels to join. And you should mark one as the trivia
channel.

You can also optionally configure a timeout and a trivia data file. (In a
pickled format). By default it uses the /pyHoNBot/trivadb file and does not
timeout.

For example:

  # In the /.honbot/default.py
  owner = ['my_hon_account_name', 'second_account_name']

  channels = ['my_hon_trivia_channel_example']
  trivia_channel = 'my_hon_trivia_channel_example'  # This maps to the in-game channel.

  # Optional
  trivia_timeout = 120  # Number of seconds to wait before stopping trivia, if
                        # no one enters any text in the chat channel.
  trivia_dir = 'path/to/trivia'  # Path to directory with the question files.


Once this is configured, you can join the same channel as your bot, using one of
the accounts on the owners list, and issue the following commands:

!trivia start
!trivia stop

They will start and stop the trivia bot accordingly. By default, the bot will
loop through all the questions once it reaches the end. Then it will shuffle
again and start at the top of the list.

The trivia files are just simple text files in the format:

  Question goes here?
  answer

  # This file can support comments also.
  Another question goes here?
  answer2

To reload the questions while the bot is running, you can use the
`!trivia reload` command.
"""
import os
import pickle
import threading
import time

from hon.packets import ID
from random import shuffle

class Trivia:
  def __init__(self, bot):
    self.bot = bot
    self.timeout_thread = None  # Used to track the timeout asynchronously.
    self.hint_thread = None  # Used to print out hints asynchronously.
    self.current = {}
    self.questions = []  # Holds all the questions. It is shuffled upon reset.
    self.used_questions = []  # As we pop off questions, they get queued here.
    self.running = False  # Marks if the trivia but is actually active or not.
    self.channel = bot.config.trivia_channel
    self.answered = False
    self.nickname_of_answerer = None
    self.last_action = 0  # Used by the threads threads to handle timeout.
    self.load()

  def load(self):
    directory = self.bot.config.trivia_dir
    if os.path.exists(directory):
      for filename in os.listdir(directory):
        if filename.endswith('.txt'):
          self.parseFile(directory + '/' + filename)
    else:
      print 'Error: Trivia file {} not found'.format(self.bot.config.trivia_file)
      self.questions = []

  def parseFile(self, file_path):
    """
    This method parses a trivial file by ignoring any comments or blank lines.
    It expects the format of Question\nAnswer pairs. Everything else separated
    by newlines.
    """
    count = -1
    question = {}
    for line in open(file_path):
      current_line = line.strip()
      if not current_line:
        continue
      if current_line.startswith('#'):
        continue
      count = count + 1
      if count % 2 == 0:
        question = {}
        question['question'] = current_line
      else:
        question['answer'] = current_line
        self.questions.append(question)


  def timeout(self):
    """
    This runs on a background thread. If, at any point, no one tries to answer
    the questions for the duration of time, we will prematurely exit trivia.

    Note: By default this is not run. You can set this to run by setting the
    'trivia_timeout' field in the configuration file for your bot.
    """
    while True:
      running = self.running
      if not running:
        continue
      last_interaction = self.last_action
      if last_interaction <= 0:
        return
      if ((last_interaction + self.bot.config.trivia_endtimeout) <= time.time()):
        self.stop(True)
        continue
      time.sleep(1)

  def recvMsg(self, bot, origin, data):
    t = time.time()
    self.last_action = t

    running = self.running
    if not running or not self.current or self.answered:
      return
    if data.lower() == self.current['answer'].lower():
      nickname = bot.id2nick[origin[1]]
      self.nickname_of_answerer = nickname
      self.answered = True

  def sendMsg(self, message):
    """Send messages in HoN chat channel on behalf of the trivia."""
    chan = self.bot.chan2id[self.channel]
    self.bot.write_packet( ID.HON_SC_CHANNEL_EMOTE, "Trivia: ^w" + message, chan )

  def askQuestionAndShowHints(self):
    """
    Displays hints periodically or until the question is answered. If a correct
    answer is flagged by recvMsg, then we stop early and award points.

    Note: This method loops forever and is intended to be execute on
    self.hint_thread.

    Example:
      Answer is "pizza".

      Hint 1:
        ---z-
      Hint 2:
        -i-z-
      Hint 3:
        pi-z-
      Hint 4:
        pi-za
      Hint 5:
        pizza  # Out of guesses, move to next question.
    """
    while(True):
      # 0. Do nothing while trivia is down
      running = self.running
      if not running:
        continue

      # 1. Get a question.
      self.nextQuestion()

      # 2. Create the string to handle hints.
      hint_chars = ['-'] * len(self.current['answer'])  # Creates an array with hypens for each character.
      hint_indices = range(0, len(hint_chars))
      shuffle(hint_indices)

      # 3. Loop through each letter, waiting a bit, and printing out a hint. If
      #    either we run out of hints, or the self.answered flag is set, then
      #    we exit the hint loop and move on to the next question.
      for i in range(0, len(hint_indices)):
        hint_index = hint_indices[i]
        delay_between_hints = time.time() + 8
        while time.time() < delay_between_hints:  # Busy loop to stall.
          answered = self.answered
          running = self.running
          if answered or not running:
            break
        answered = self.answered
        if answered:
          nickname = self.nickname_of_answerer
          self.sendMsg( "^y{0} ^wgot it right! The answer was: ^g{1}".format( nickname, self.current['answer'] ) )
          print ( "Trivia - Nick: {0} Question: {1} Answer: {2}".format( nickname, self.current['question'], self.current['answer'] ) )
          # TODO(mrhappyasthma): Scoring.
          break
        if i < (len(hint_indices) - 1):
          hint_chars[hint_index] = self.current['answer'][hint_index]
          self.sendMsg(''.join(hint_chars))
        else:
          print ( "Trivia - Unanswered Question: {0} Answer: {1}".format(self.current['question'], self.current['answer'] ) )
          self.sendMsg( "^rNo one ^wgot it. ^t:'( ^wThe answer was: ^g{0}".format(self.current['answer'] ) )
      time.sleep(3)
      self.sendMsg( "Get ready for the next question!" )
      self.answered = False
      self.nickname_of_answerer = None
      time.sleep(10)

  def nextQuestion(self):
    """Get the next question from the shuffled list. If we are out, reset first."""
    if len(self.questions) == 0:
      self.reset()
      self.current = self.questions.pop()
      question = self.current['question']
      self.sendMsg(question)
      print 'Trivia - Asking "{}" with {} questions left and {} used'.format(question, len(self.questions), len(self.used_questions))
      return

    if self.current:
      self.used_questions.append(self.current)
    self.current = self.questions.pop()
    question = self.current['question']
    print 'Trivia - Asking "{}" with {} questions left and {} used'.format(question, len(self.questions), len(self.used_questions))
    self.sendMsg(question)

  def start(self):
    """Starts the trivia bot."""
    running = self.running
    if running:
      return
    self.running = True
    self.reset()
    self.sendMsg("Started")
    time.sleep(3)
    if self.bot.config.trivia_timeout:
      if not self.timeout_thread:
        self.timeout_thread = threading.Thread(target=self.timeout)
        self.timeout_thread.start()
    if not self.hint_thread:
      self.hint_thread = threading.Thread(target=self.askQuestionAndShowHints)
      self.hint_thread.start()

  def stop(self, activity=False):
    """Stops the trivia bot."""
    running = self.running
    if not running:
      return
    self.running = False
    self.reset()
    if activity:
      self.sendMsg("Stopped due to inactivity")
    else:
      self.sendMsg("Stopping...")

  def reset(self):
    """Reset any used questions, and shuffle again."""
    self.questions = self.questions + self.used_questions
    self.used_questions = []
    shuffle(self.questions)
    self.last_action = 0
    self.answered = False
    self.nickname_of_answerer = None


def receivemessage(bot, origin, data):
  """
  Whenever we receive a message, check if the trivia is running. If so, handle
  the message.
  """
  if bot.trivia.channel in bot.chan2id:
    if origin[2] == bot.chan2id[bot.trivia.channel]:
      running = bot.trivia.running
      if not running:
        return
      bot.trivia.recvMsg(bot, origin, data)


receivemessage.event = [ID.HON_SC_CHANNEL_MSG]
receivemessage.priority = 'high'
receivemessage.thread = True


def trivia(bot, input):
  """Initialize the bot with the '!trivia start' and '!trivia stop' commands."""
  if input.origin[2] != bot.chan2id[bot.trivia.channel]:
    bot.say("^wThis only works in the HoNTrivia channel.")
    return
  if not input.group(2):
    bot.say("^wAccepted arguments are ^gstart ^wand ^rstop^w.")
  else:
    if input.group(2) == "start":
      bot.trivia.start()
    elif input.group(2) == "stop":
      if input.admin:
        bot.trivia.stop()
      else:
        bot.say("^wOnly an admin can use stop. It will stop automatically after inactivity.")
trivia.commands = ['trivia']


def setup(bot):
  """
  This is the main entry point into the module. We will load some default crap,
  in case they are not overridden in the config.

  Lastly create the bot object.
  """
  bot.config.module_config( 'trivia_channel', ['hontrivia', 'Set the channel the trivia bot will work in'] )
  bot.config.module_config( 'trivia_file', ['triviadb', 'Set the channel the trivia bot will work in'] )
  bot.config.module_config( 'trivia_timeout', [-1, 'Set the timeout for trivia'] )

  bot.trivia = Trivia(bot)


if __name__ == '__main__':
    print __doc__.strip()
