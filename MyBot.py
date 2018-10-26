#!/usr/bin/env python3

import sys
import hlt
from hlt import constants, Direction
import logging
import random
from bisect import bisect_left


def binary_search(a, x, low=0, high=None):
    high = high if high is not None else len(a)
    pos = bisect_left(a, x, low, high)
    return (pos if pos != high and a[pos] == x else -1)


class Brain:
    def __init__(self, game):
        """
        Object containing all strategy.
        """
        self.game = game
        self.ship_status = {}
        self.spawn_cutoff = constants.MAX_TURNS * 0.5
        self.return_amount = constants.MAX_HALITE * 0.8

    def take_turn(self):
        self.start_turn()
        self.move_ships()
        self.spawn()
        self.end_turn()

    def start_turn(self):
        self.game.update_frame()
        self.map = self.game.game_map
        self.me = self.game.me
        self.command_queue = []

        if self.map[self.me.shipyard].is_occupied:
            self.map[self.me.shipyard].mark_unsafe()

    def spawn(self):
        if (self.me.halite_amount >= constants.SHIP_COST and
                self.map[self.me.shipyard].safe and
                self.game.turn_number < self.spawn_cutoff):
            self.command_queue.append(self.me.shipyard.spawn())
            self.map[self.me.shipyard].mark_unsafe()

    def end_turn(self):
        self.game.end_turn(self.command_queue)

    def ship_binary_search(self, ships, id):
        ship_ids = list(map(lambda x: x.id, ships))
        return binary_search(ship_ids, id)

    def ship_can_move(self, ship):
        return ship.halite_amount >= self.map[ship.position].move_cost()

    def on_shipyard(self, ship):
        return self.map[self.me.shipyard].position == ship.position

    def update_ship_status(self, ship):
        if ship.id not in self.ship_status or ship.position == self.me.shipyard.position:
            self.ship_status[ship.id] = "exploring"
        elif ship.halite_amount >= self.return_amount:
            self.ship_status[ship.id] = "returning"

    def get_move(self, ship):
        if self.ship_status[ship.id] == "exploring":
            return self.explore(ship)
        else:
            return self.return_to_yard(ship)

    def explore(self, ship):
        if self.on_shipyard(ship):
            position = self.get_random_safe(ship).position
            direction = self.map.get_unsafe_moves(ship.position, position)[0]
            return (position, direction)

        max_cell = self.get_max_safe_adjacent(ship)
        max_direction = self.map.get_unsafe_moves(ship.position, max_cell.position)[0]
        current_amount = self.map[ship.position].halite_amount

        move_outlook = max_cell.halite_amount / 4 - self.map[ship].move_cost()
        stay_outlook = current_amount - (current_amount * 3/4 * 3/4)
        should_move = move_outlook >= stay_outlook

        if not should_move and self.map[ship.position].safe:
            return (ship.position, Direction.Still)
        else:
            return (max_cell.position, max_direction)

    def return_to_yard(self, ship):
        return self.get_safe_to_destination(ship, self.me.shipyard.position)

    # find the least costly, safe move towards destination
    def get_safe_to_destination(self, ship, destination):
        best_move = None
        best_cost = sys.maxsize

        for direction in self.map.get_unsafe_moves(ship.position, destination):
            target_pos = ship.position.directional_offset(direction)
            if self.map[target_pos].safe:
                move_cost = self.map[target_pos].move_cost()
                if move_cost < best_cost:
                    best_cost = move_cost
                    best_move = (target_pos, direction)

        # best safe move in right direction
        if best_move is not None:
            return best_move
        # stay still
        elif self.map[ship].safe:
            return (ship.position, Direction.Still)
        # least costly and safe adjacent
        else:
            min_cell = self.get_min_safe_adjacent(ship)
            min_direction = self.map.get_unsafe_moves(ship.position, min_cell.position)[0]
            return (min_cell.position, min_direction)

    def get_best_adjacent(self, ship, find_max):
        safe = self.map.get_safe_adjacent(ship.position)
        safe.sort(key=lambda x: x.halite_amount, reverse=find_max)

        best = safe[0].halite_amount
        equal = []

        for cell in safe:
            if cell.halite_amount == best:
                equal.append(cell)
            else:
                break

        if not len(equal):
            raise ValueError('No safe adjacent positions!')

        return random.choice(equal)

    def get_min_safe_adjacent(self, ship):
        return self.get_best_adjacent(ship, False)

    def get_max_safe_adjacent(self, ship):
        return self.get_best_adjacent(ship, True)

    def get_random_safe(self, ship):
        return random.choice(self.map.get_safe_adjacent(ship.position))

    def move_ships(self):
        movable_ships = []

        for ship in self.me.get_ships():
            self.update_ship_status(ship)

            # find ships that can't move
            if not self.ship_can_move(ship):
                self.map[ship].mark_unsafe()
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

            self.map[position].mark_unsafe()
            self.command_queue.append(ship.move(direction))

            # If ship just moved onto the current position of a ship that has
            # not moved yet, then move that ship next. This ensures the ship
            # will not end up with no safe moves.
            existing_ship = self.map[position].ship
            if existing_ship:
                j = self.ship_binary_search(movable_ships[i+1:], existing_ship.id)
                if j > i+1:
                    temp = movable_ships[i+1]
                    movable_ships[i+1] = movable_ships[j]
                    movable_ships[j] = temp


def main():
    game = hlt.Game()
    # This is a good place to do computationally expensive start-up pre-processing.
    # As soon as you call "ready" function below, the 2 second per turn timer will start.
    game.ready("NewBot")
    brain = Brain(game)

    while True:
        brain.take_turn()


if __name__ == "__main__":
    main()
