#!/usr/bin/env python3

import sys
import hlt
from hlt import constants, Direction, Position
import logging
import random
from scipy import ndimage
from bisect import bisect_left
import matplotlib.pyplot as plt


def binary_search(a, x, low=0, high=None):
    high = high if high is not None else len(a)
    pos = bisect_left(a, x, low, high)
    return (pos if pos != high and a[pos] == x else -1)


class Brain:
    def __init__(self, game):
        self.game = game
        self.ship_status = {}
        self.spawn_cutoff = constants.MAX_TURNS * 1/2
        self.return_amount = constants.MAX_HALITE * 0.8

    def start_turn(self):
        self.game.update_frame()
        self.map = self.game.game_map
        self.me = self.game.me
        self.unsafe = {}
        self.command_queue = []
        self.made_dropoff_this_turn = False
        self.dropoff_dist_threshold = self.map.width / 2

        # check for spawns
        if not self.shipyard_free:
            self.mark_unsafe(self.me.shipyard.position)

        #  self.filtered = []
        #  self.filter()

    #  def filter(self):
    #      raw = []
    #      for y in range(self.map.height):
    #          row = []
    #          for x in range(self.map.width):
    #              row.append(self.map[Position(x, y)].halite_amount)
    #          raw.append(row)
    #
    #      self.filtered = ndimage.uniform_filter(raw, size=5, mode='wrap').tolist()

    #  def get_filter_val(self, p):
    #      normalized = self.map.normalize(p)
    #      return self.filtered[normalized.y][normalized.x]

    def ship_binary_search(self, ships, id):
        ship_ids = list(map(lambda x: x.id, ships))
        return binary_search(ship_ids, id)

    def mark_unsafe(self, p):
        normalized = self.map.normalize(p)
        self.unsafe[(normalized.x, normalized.y)] = None

    def position_is_safe(self, p):
        normalized = self.map.normalize(p)
        return (normalized.x, normalized.y) not in self.unsafe

    def on_dropoff(self, ship):
        dropoffs = self.get_all_dropoffs()

        for dropoff in dropoffs:
            if ship.position == dropoff.position:
                return True

        return False

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

    def get_all_dropoffs(self):
        dropoffs = self.me.get_dropoffs()
        dropoffs.append(self.me.shipyard)
        return dropoffs

    def find_closest_dropoff(self, ship):
        dropoffs = self.get_all_dropoffs()

        closest = None
        least_dist = sys.maxsize
        for dropoff in dropoffs:
            dist = self.map.calculate_distance(ship.position, dropoff.position)
            if dist < least_dist:
                least_dist = dist
                closest = dropoff.position

        return closest

    def update_status(self, ship):
        if ship.id not in self.ship_status or self.on_dropoff(ship):
            self.ship_status[ship.id] = "exploring"
        elif ship.halite_amount >= self.return_amount:
            self.ship_status[ship.id] = "returning"

    def get_move(self, ship):
        if self.ship_status[ship.id] == "exploring":
            return self.explore(ship)
        else:
            return self.return_to_dropoff(ship)

    def explore(self, ship):
        if self.on_dropoff(ship):
            random_position, random_direction, _ = self.get_random_safe(ship)
            return (random_position, random_direction)

        # get the best direction given our filtered halite values
        #  max_position, max_direction, _ = self.get_filter_max_safe_adjacent(ship)
        max_position, max_direction, _ = self.get_max_safe_adjacent(ship)

        # determine if best to move or stay based on actual amounts
        max_amount = self.map[max_position].halite_amount
        current_amount = self.map[ship.position].halite_amount

        move_outlook = max_amount / 4 - self.move_cost(ship.position)
        stay_outlook = current_amount - (current_amount * 3/4 * 3/4)
        should_move = move_outlook >= stay_outlook

        if not should_move and self.position_is_safe(ship.position):
            return (ship.position, Direction.Still)
        else:
            return (max_position, max_direction)

    def return_to_dropoff(self, ship):
        closest_dropoff = self.find_closest_dropoff(ship)
        return self.get_safe_to_destination(ship, closest_dropoff)

    def ship_can_move(self, ship):
        return ship.halite_amount >= self.move_cost(ship.position)

    def move_cost(self, position):
        return (self.map[position].halite_amount) / 10

    # find the least costly, safe move towards destination
    def get_safe_to_destination(self, ship, destination):
        best_move = None
        best_cost = sys.maxsize

        for direction in self.map.get_unsafe_moves(ship.position, destination):
            target_pos = ship.position.directional_offset(direction)
            if self.position_is_safe(target_pos):
                move_cost = self.move_cost(target_pos)
                if move_cost < best_cost:
                    best_cost = move_cost
                    best_move = (target_pos, direction)

        # best safe move in right direction
        if best_move is not None:
            return best_move
        # stay still
        elif self.position_is_safe(ship.position):
            return (ship.position, Direction.Still)
        # least costly and safe adjacent
        else:
            (min_position, min_direction, _) = self.get_min_safe_adjacent(ship)
            return (min_position, min_direction)

    def get_all_safe_adjacent(self, ship):
        out = []
        for direction in Direction.get_all_cardinals():
            position = ship.position.directional_offset(direction)
            if self.position_is_safe(position):
                amount = self.map[position].halite_amount
                out.append((position, direction, amount))

        if len(out) > 0:
            return out

        raise ValueError('No safe adjacent positions!')

    def get_min_safe_adjacent(self, ship):
        safe = self.get_all_safe_adjacent(ship)

        safe.sort(key=lambda x: x[2], reverse=False)
        min = safe[0][2]
        equal = []

        for adj in safe:
            if adj[2] == min:
                equal.append(adj)
            else:
                break

        return random.choice(equal)

    #  def get_filter_max_safe_adjacent(self, ship):
    #      safe = self.get_all_safe_adjacent(ship)
    #
    #      filtered = []
    #      for adj in safe:
    #          filtered.append((adj[0], adj[1], self.get_filter_val(adj[0])))
    #
    #      filtered.sort(key=lambda x: x[2], reverse=True)
    #      return filtered[0]

    def get_max_safe_adjacent(self, ship):
        safe = self.get_all_safe_adjacent(ship)

        safe.sort(key=lambda x: x[2], reverse=True)
        max = safe[0][2]
        equal = []

        for adj in safe:
            if adj[2] == max:
                equal.append(adj)
            else:
                break

        return random.choice(equal)

    def get_random_safe(self, ship):
        return random.choice(self.get_all_safe_adjacent(ship))

    def should_become_dropoff(self, ship):
        return False  # TODO
        #  if self.made_dropoff_this_turn:
        #      return False

        #  closest_dropoff = self.find_closest_dropoff(ship)
        #  dropoff_dist = self.map.calculate_distance(closest_dropoff, ship.position)
        #
        #  if (self.me.halite_amount >= constants.DROPOFF_COST and
        #          dropoff_dist > self.dropoff_dist_threshold):
        #          self.made_dropoff_this_turn = True
        #          return True

    def move_ships(self):
        movable_ships = []

        for ship in self.me.get_ships():
            self.update_status(ship)
            if self.should_become_dropoff(ship):
                self.command_queue.append(ship.make_dropoff())
            elif not self.ship_can_move(ship):
                self.mark_unsafe(ship.position)
                self.command_queue.append(ship.stay_still())
            else:
                movable_ships.append(ship)

        # sort ships by id
        movable_ships.sort(key=lambda x: x.id)

        for i, ship in enumerate(movable_ships):
            try:
                position, direction = self.get_move(ship)
            except Exception:
                position = ship.position
                direction = Direction.Still

            self.mark_unsafe(position)
            self.command_queue.append(ship.move(direction))

            # If ship just moved onto the current position of a ship that has
            # not moved, then move that ship next. This ensures this ship will
            # not end up with no safe moves.
            existing_ship = self.map[position].ship
            if existing_ship:
                j = self.ship_binary_search(movable_ships[i+1:], existing_ship.id)
                if j > i+1:
                    temp = movable_ships[i+1]
                    movable_ships[i+1] = movable_ships[j]
                    movable_ships[j] = temp

    def end_turn(self):
        logging.info(self.command_queue)
        self.game.end_turn(self.command_queue)


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
