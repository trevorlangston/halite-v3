#!/usr/bin/env python3

import hlt
from hlt import constants, Direction
import random
import logging


class Brain:
    def __init__(self, game):
        self.game = game
        self.ship_status = {}
        self.spawn_cutoff = constants.MAX_TURNS * 3/4
        self.return_amount = constants.MAX_HALITE * 0.8

    def start_turn(self):
        self.game.update_frame()
        self.map = self.game.game_map
        self.me = self.game.me
        self.unsafe = {}
        self.command_queue = []

        if not self.shipyard_free:
            self.mark_unsafe(self.me.shipyard.position)

    def mark_unsafe(self, p):
        self.unsafe[(p.x, p.y)] = None

    def position_is_safe(self, p):
        return (p.x, p.y) not in self.unsafe

    def shipyard_free(self):
        return not self.map[self.me.shipyard].is_occupied

    def spawn_safe(self):
        return self.position_is_safe(self.me.shipyard.position)

    def spawn(self):
        if (self.me.halite_amount >= constants.SHIP_COST and
                self.position_is_safe(self.me.shipyard.position) and
                self.game.turn_number < self.spawn_cutoff):
            self.command_queue.append(self.me.shipyard.spawn())
            self.mark_unsafe(self.map[self.me.shipyard].position)

    def move_ships(self):
        movable_ships = []

        for ship in self.me.get_ships():
            # first find ships that cannot move
            if not self.ship_can_move(ship):
                self.mark_unsafe(ship.position)
                self.ships.remove(ship)
                self.command_queue.append(ship.stay_still())
            else:
                movable_ships.append(ship)

        for ship in movable_ships:
            self.command_queue.append(self.get_move(ship))

    def get_move(self, ship):
        (position, direction) = self.get_random_safe(ship)
        self.mark_unsafe(position)
        return ship.move(direction)

    def ship_can_move(self, ship):
        return ship.halite_amount >= self.move_cost(ship)

    def move_cost(self, ship):
        return (self.map[ship.position].halite_amount) / 10

    def get_random_safe(self, ship):
        out = []
        for direction in Direction.get_all_cardinals():
            position = ship.position.directional_offset(direction)
            if self.position_is_safe(position):
                out.append((position, direction))

        return random.choice(out)

    def end_turn(self):
        logging.info(self.command_queue)
        self.game.end_turn(self.command_queue)

    #  def update_status(self, ship):
    #      if ship.id not in self.ship_status or ship.position == self.me.shipyard.position:
    #          self.ship_status[ship.id] = "exploring"
    #      elif ship.is_full or ship.halite_amount >= self.return_amount:
    #          self.ship_status[ship.id] = "returning"

    #  def get_max_safe_adjacent(self, ship):
    #      max_position = None
    #      max = 0
    #
    #      for p in ship.position.get_surrounding_cardinals():
    #          if self.position_is_safe(p):
    #              amount = self.map[p].halite_amount
    #              if amount >= max:
    #                  max = amount
    #                  max_position = p
    #
    #      return max_position

    #  def get_move(self, ship):
        #  if self.ship_status[ship.id] == "exploring":
        #      position_amount = self.map[ship.position].halite_amount
        #      cost_to_move = int(position_amount / 10)
        #      can_move = self.budget > cost_to_move
        #
        #      max_adjacent = self.get_max_safe_adjacent(ship)
        #      max_amount = self.map[max_adjacent].halite_amount
        #
        #      move_outlook = max_amount / 4 - cost_to_move
        #      stay_outlook = position_amount - (position_amount * 3/4 * 3/4)
        #
        #      if can_move and (ship.position == self.me.shipyard.position or move_outlook > stay_outlook):
        #          dest = max_adjacent
        #          self.budget -= cost_to_move
        #      elif not self.position_is_safe(ship.position):
        #          dest = max_adjacent
        #          self.budget -= cost_to_move
        #      else:
        #          dest = ship.position
        #
        #  else:
        #      dest = self.me.shipyard.position

        #  position_amount = self.map[ship.position].halite_amount
        #  cost_to_move = int(position_amount / 10)
        #  can_move = self.budget >= cost_to_move
        #  dest = self.get_random_safe(ship)
        #  if can_move:
        #      self.add_next_position(dest)
        #      return self.map.naive_navigate(ship, dest)
        #
        #  return ship.move("o")


def main():
    game = hlt.Game()
    # This is a good place to do computationally expensive start-up pre-processing.
    # As soon as you call "ready" function below, the 2 second per turn timer will start.
    game.ready("MyPythonBot")

    brain = Brain(game)

    while True:
        brain.start_turn()
        brain.move_ships()
        brain.spawn()
        brain.end_turn()


if __name__ == "__main__":
    main()
