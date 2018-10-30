#!/bin/sh

rm replays/*
./halite --replay-directory replays/ -vvv --width 32 --height 32 "python3 latest.py" "python3 v3.py"
