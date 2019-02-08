#!/usr/bin/env python3

import sys
import hlt
from hlt import constants, Direction, Position
import logging
import random
import operator
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
        self.spawn_cutoff = constants.MAX_TURNS * 1/2
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
        self.is_end_game = False

        self.process_enemies()

        # determine if we are in 'endgame'
        self.turns_left = constants.MAX_TURNS - self.game.turn_number
        turns_to_bring_home = int(len(self.me.get_ships()) / len(self.get_all_dropoffs()))
        if turns_to_bring_home >= self.turns_left:
            self.is_end_game = True

    def process_enemies(self):
        inspired = {}
        for player in self.game.players:
            if player is not self.game.my_id:
                for ship in self.game.players[player].get_ships():
                    # mark current enemy positions as unsafe
                    self.map[ship].mark_unsafe()

                    #  find inspired positions
                    for row in range(-constants.INSPIRATION_RADIUS, constants.INSPIRATION_RADIUS):
                        for col in range(-constants.INSPIRATION_RADIUS, constants.INSPIRATION_RADIUS):
                            x = ship.position.x + col
                            y = ship.position.y + row
                            if (x, y) in inspired:
                                inspired[(x, y)] += 1
                            else:
                                inspired[(x, y)] = 1

        #  marks these cells as being 'inspiring' to ships
        for x_y_tuple, ship_count in inspired.items():
            if ship_count >= 2:
                position = Position(x_y_tuple[0], x_y_tuple[1])
                self.map[position].mark_inspired()

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

    def should_become_dropoff(self, ship):
        return False  # TODO

    def ship_can_move(self, ship):
        return ship.halite_amount >= self.map[ship.position].move_cost()

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

    def is_dropoff(self, position):
        return self.map[position].has_structure

    def on_dropoff(self, ship):
        dropoffs = self.get_all_dropoffs()

        for dropoff in dropoffs:
            if ship.position == dropoff.position:
                return True

        return False

    def should_return(self, ship):
        # ship should not go so far from dropoff that it can't return by end of game
        closest_dropoff = self.find_closest_dropoff(ship)
        dist_to_closest = self.map.calculate_distance(ship.position, closest_dropoff)
        out_of_moves = dist_to_closest >= self.turns_left + 1

        # ship should return if full
        ship_full = ship.halite_amount >= self.return_amount

        return self.is_end_game or out_of_moves or ship_full

    def update_ship_status(self, ship):
        if self.should_return(ship):
            self.ship_status[ship.id] = "returning"
        elif ship.id not in self.ship_status or self.on_dropoff(ship):
            self.ship_status[ship.id] = "exploring"

    def get_move(self, ship):
        if self.ship_status[ship.id] == "exploring":
            return self.explore(ship)
        else:
            return self.return_to_dropoff(ship)

    def get_best_dir(self, ship):
        directions = {
                Direction.North: 0,
                Direction.South: 0,
                Direction.East: 0,
                Direction.West: 0
                }

        for row in range(-10, 10):
            for col in range(-10, 10):
                if col == 0 and row == 0: continue

                pos = Position(ship.position.x + col, ship.position.y + row)
                dist = self.map.calculate_distance(ship.position, pos)
                pull = self.map[pos].halite_amount / dist**2
                if self.map[pos].inspired:
                    pull *= (constants.INSPIRED_BONUS_MULTIPLIER + 1)

                for move in self.map.get_unsafe_moves(ship.position, pos):
                    directions[move] += pull

        best_safe = None
        while len(directions):
            best_direction = max(directions.items(), key=operator.itemgetter(1))[0]
            directions.pop(best_direction)
            cell = self.map[ship.position.directional_offset(best_direction)]
            if cell.safe:
                best_safe = cell
                break

        if best_safe is None:
            raise ValueError('No safe adjacent positions!')

        return best_safe

    def explore(self, ship):
        best_cell = self.get_best_dir(ship)
        best_direction = self.map.get_unsafe_moves(ship.position, best_cell.position)[0]

        best_amount = best_cell.halite_amount
        if best_cell.inspired:
            best_amount *= (constants.INSPIRED_BONUS_MULTIPLIER + 1)

        current_amount = self.map[ship.position].halite_amount
        if self.map[ship.position].inspired:
            current_amount *= (constants.INSPIRED_BONUS_MULTIPLIER + 1)

        move_outlook = best_amount / 4 - self.map[ship].move_cost()
        stay_outlook = current_amount - (current_amount * 3/4 * 3/4)
        should_move = move_outlook >= stay_outlook

        if not should_move and self.map[ship.position].safe:
            return (ship.position, Direction.Still)
        else:
            return (best_cell.position, best_direction)

    def return_to_dropoff(self, ship):
        destination = self.find_closest_dropoff(ship)
        best_move = None
        best_cost = sys.maxsize

        for direction in self.map.get_unsafe_moves(ship.position, destination):
            target_pos = ship.position.directional_offset(direction)

            if self.is_dropoff(target_pos) and self.is_end_game:
                best_move = (target_pos, direction)
                break

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

    def get_random_safe(self, ship):
        return random.choice(self.map.get_safe_adjacent(ship.position))

    def move_ships(self):
        movable_ships = []

        for ship in self.me.get_ships():
            self.update_ship_status(ship)

            # find ships that can't move
            if self.should_become_dropoff(ship):
                self.command_queue.append(ship.make_dropoff())
            elif not self.ship_can_move(ship):
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
                logging.info(Exception)
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
    game.ready("v6")
    brain = Brain(game)

    logging.info(constants.INSPIRATION_RADIUS)
    logging.info(constants.INSPIRATION_ENABLED)
    logging.info(constants.INSPIRATION_SHIP_COUNT)
    logging.info(constants.INSPIRED_EXTRACT_RATIO)
    logging.info(constants.INSPIRED_BONUS_MULTIPLIER)
    logging.info(constants.INSPIRED_MOVE_COST_RATIO)

    while True:
        brain.take_turn()


if __name__ == "__main__":
    main()
