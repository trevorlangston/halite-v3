#!/bin/sh

rm replays/*
./halite --replay-directory replays/ -vvv --width 64 --height 64 "python3 MyBot.py" "python3 v6.py"
